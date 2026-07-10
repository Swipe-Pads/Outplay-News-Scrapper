"""Tests for src/mailer.py + src/email_template.py (mocked Cloudflare/Shopify HTTP)."""

import hashlib
import hmac as hmac_lib
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, call

from src.config import Config
from src.mailer import (
    EmailProvider,
    CloudflareEmailProvider,
    MailerError,
    unsubscribe_token,
    unsubscribe_url,
    get_subscribers,
    get_suppressed_emails,
    send_mailing,
    load_mailed_ids,
    record_mailed_id,
    run_weekly_mailing,
    MAX_SEND_RETRIES,
)
from src.email_template import render_email, PHYSICAL_ADDRESS_PLACEHOLDER


@pytest.fixture(autouse=True)
def mail_env(monkeypatch):
    monkeypatch.setattr(Config, 'CF_ACCOUNT_ID', 'acct123')
    monkeypatch.setattr(Config, 'CF_EMAIL_API_TOKEN', 'cf-token')
    monkeypatch.setattr(Config, 'KV_NAMESPACE_ID', 'kv456')
    monkeypatch.setattr(Config, 'MAIL_FROM', 'digest@mail.outplay.game')
    monkeypatch.setattr(Config, 'MAIL_FROM_NAME', 'SwipePads Weekly')
    monkeypatch.setattr(Config, 'MAIL_RATE_PER_SEC', 5.0)
    monkeypatch.setattr(Config, 'UNSUBSCRIBE_BASE_URL', 'https://unsub.example.com')
    monkeypatch.setattr(Config, 'UNSUB_SECRET', 'test-secret')


def _mock_response(json_data, status_code=200, ok=None, text=''):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = ok if ok is not None else (200 <= status_code < 300)
    resp.json.return_value = json_data
    resp.text = text or json.dumps(json_data)
    resp.raise_for_status.return_value = None
    return resp


class _FakeProvider(EmailProvider):
    def __init__(self):
        self.sent = []

    def send(self, to, subject, html, headers=None):
        self.sent.append({'to': to, 'subject': subject, 'html': html, 'headers': headers})
        return f"msg-{len(self.sent)}"


# === Unsubscribe URL / HMAC ===

class TestUnsubscribe:
    def test_token_is_hmac_sha256_of_lowercased_email(self):
        expected = hmac_lib.new(
            b'test-secret', b'gamer@example.com', hashlib.sha256
        ).hexdigest()
        assert unsubscribe_token('  Gamer@Example.COM ') == expected

    def test_url_contains_email_and_token(self):
        url = unsubscribe_url('gamer@example.com')
        token = unsubscribe_token('gamer@example.com')
        assert url.startswith('https://unsub.example.com?e=gamer%40example.com&t=')
        assert url.endswith(token)

    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.setattr(Config, 'UNSUB_SECRET', '')
        with pytest.raises(MailerError):
            unsubscribe_token('a@b.com')

    def test_missing_base_url_raises(self, monkeypatch):
        monkeypatch.setattr(Config, 'UNSUBSCRIBE_BASE_URL', '')
        with pytest.raises(MailerError):
            unsubscribe_url('a@b.com')


# === Cloudflare provider ===

class TestCloudflareEmailProvider:
    @patch('src.mailer.requests.post')
    def test_send_payload_shape_and_message_id(self, mock_post):
        # REST named-address shape: {"address", "name"} per
        # https://developers.cloudflare.com/email-service/examples/email-sending/recipients/
        mock_post.return_value = _mock_response(
            {'success': True, 'result': {'message_id': 'abc-123', 'delivered': []}}
        )

        provider = CloudflareEmailProvider()
        msg_id = provider.send(
            'gamer@example.com', 'Subject', '<p>Hi</p>',
            headers={'List-Unsubscribe': '<https://u>'}
        )

        assert msg_id == 'abc-123'
        url = mock_post.call_args[0][0]
        assert url == (
            'https://api.cloudflare.com/client/v4/accounts/acct123/email/sending/send'
        )
        assert mock_post.call_args[1]['headers']['Authorization'] == 'Bearer cf-token'
        payload = mock_post.call_args[1]['json']
        assert payload['from'] == {
            'address': 'digest@mail.outplay.game', 'name': 'SwipePads Weekly'
        }
        assert payload['to'] == 'gamer@example.com'
        assert payload['subject'] == 'Subject'
        assert payload['html'] == '<p>Hi</p>'
        assert payload['headers'] == {'List-Unsubscribe': '<https://u>'}

    @patch('src.mailer.time.sleep')
    @patch('src.mailer.requests.post')
    def test_retries_on_429_then_succeeds(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _mock_response({}, status_code=429, ok=False),
            _mock_response({'success': True, 'result': {'message_id': 'ok-1'}}),
        ]
        provider = CloudflareEmailProvider()
        assert provider.send('a@b.com', 'S', '<p>x</p>') == 'ok-1'
        assert mock_post.call_count == 2
        assert mock_sleep.called

    @patch('src.mailer.time.sleep')
    @patch('src.mailer.requests.post')
    def test_retries_on_5xx_then_fails(self, mock_post, mock_sleep):
        mock_post.return_value = _mock_response({}, status_code=503, ok=False)
        provider = CloudflareEmailProvider()
        with pytest.raises(MailerError):
            provider.send('a@b.com', 'S', '<p>x</p>')
        assert mock_post.call_count == MAX_SEND_RETRIES

    @patch('src.mailer.requests.post')
    def test_4xx_fails_without_retry(self, mock_post):
        mock_post.return_value = _mock_response({}, status_code=400, ok=False)
        provider = CloudflareEmailProvider()
        with pytest.raises(MailerError):
            provider.send('a@b.com', 'S', '<p>x</p>')
        assert mock_post.call_count == 1

    def test_missing_config_clear_errors(self, monkeypatch):
        monkeypatch.setattr(Config, 'CF_ACCOUNT_ID', '')
        with pytest.raises(MailerError) as exc:
            CloudflareEmailProvider()
        assert 'CF_ACCOUNT_ID' in str(exc.value)


# === Subscribers (Shopify GraphQL) ===

class TestGetSubscribers:
    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher._get_domain')
    @patch('src.mailer.requests.post')
    def test_paginates_and_filters_subscribed(self, mock_post, mock_domain, mock_token):
        mock_domain.return_value = 'test.myshopify.com'
        mock_token.return_value = 'tok'
        mock_post.side_effect = [
            _mock_response({'data': {'customers': {
                'pageInfo': {'hasNextPage': True, 'endCursor': 'c1'},
                'nodes': [
                    {'email': 'a@x.com', 'emailMarketingConsent': {'marketingState': 'SUBSCRIBED'}},
                    {'email': 'b@x.com', 'emailMarketingConsent': {'marketingState': 'NOT_SUBSCRIBED'}},
                ],
            }}}),
            _mock_response({'data': {'customers': {
                'pageInfo': {'hasNextPage': False, 'endCursor': None},
                'nodes': [
                    {'email': 'c@x.com', 'emailMarketingConsent': {'marketingState': 'SUBSCRIBED'}},
                    {'email': None, 'emailMarketingConsent': {'marketingState': 'SUBSCRIBED'}},
                ],
            }}}),
        ]

        emails = get_subscribers()
        assert emails == ['a@x.com', 'c@x.com']
        assert mock_post.call_count == 2
        # graphql endpoint + cursor forwarded on page 2
        assert 'graphql.json' in mock_post.call_args_list[0][0][0]
        assert mock_post.call_args_list[1][1]['json']['variables'] == {'cursor': 'c1'}

    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher._get_domain')
    @patch('src.mailer.requests.post')
    def test_graphql_errors_raise(self, mock_post, mock_domain, mock_token):
        mock_domain.return_value = 'test.myshopify.com'
        mock_token.return_value = 'tok'
        mock_post.return_value = _mock_response({'errors': [{'message': 'denied'}]})
        with pytest.raises(MailerError):
            get_subscribers()


# === Suppression (Cloudflare KV) ===

class TestSuppression:
    @patch('src.mailer.requests.get')
    def test_reads_keys_lowercased(self, mock_get):
        mock_get.return_value = _mock_response({
            'result': [{'name': 'Gone@X.com'}, {'name': 'left@y.com'}],
            'result_info': {'cursor': ''},
        })
        assert get_suppressed_emails() == {'gone@x.com', 'left@y.com'}
        url = mock_get.call_args[0][0]
        assert 'accounts/acct123/storage/kv/namespaces/kv456/keys' in url

    @patch('src.mailer.requests.get')
    def test_kv_failure_is_graceful(self, mock_get):
        mock_get.side_effect = RuntimeError('kv down')
        assert get_suppressed_emails() == set()

    def test_unconfigured_kv_is_graceful(self, monkeypatch):
        monkeypatch.setattr(Config, 'KV_NAMESPACE_ID', '')
        assert get_suppressed_emails() == set()


# === send_mailing ===

class TestSendMailing:
    @patch('src.mailer.get_suppressed_emails')
    def test_one_email_per_recipient_with_unsub_headers(self, mock_suppressed):
        mock_suppressed.return_value = set()
        provider = _FakeProvider()

        stats = send_mailing(
            'Weekly Digest', '<p>news</p>',
            recipients=['a@x.com', 'b@x.com'],
            provider=provider, rate_per_sec=0,
        )

        assert stats['sent'] == 2
        assert [s['to'] for s in provider.sent] == ['a@x.com', 'b@x.com']
        # personalized unsubscribe link per recipient
        assert unsubscribe_token('a@x.com') in provider.sent[0]['html']
        assert unsubscribe_token('b@x.com') in provider.sent[1]['html']
        assert provider.sent[0]['headers']['List-Unsubscribe'].startswith('<https://unsub')
        assert provider.sent[0]['headers']['List-Unsubscribe-Post'] == (
            'List-Unsubscribe=One-Click'
        )

    @patch('src.mailer.get_suppressed_emails')
    def test_suppressed_recipients_skipped(self, mock_suppressed):
        mock_suppressed.return_value = {'gone@x.com'}
        provider = _FakeProvider()

        stats = send_mailing(
            'S', '<p>x</p>',
            recipients=['keep@x.com', 'Gone@X.com'],
            provider=provider, rate_per_sec=0,
        )

        assert stats['suppressed'] == 1
        assert stats['sent'] == 1
        assert [s['to'] for s in provider.sent] == ['keep@x.com']

    @patch('src.mailer.time.sleep')
    @patch('src.mailer.get_suppressed_emails')
    def test_throttle_sleeps_between_sends(self, mock_suppressed, mock_sleep):
        mock_suppressed.return_value = set()
        provider = _FakeProvider()

        send_mailing(
            'S', '<p>x</p>',
            recipients=['a@x.com', 'b@x.com', 'c@x.com'],
            provider=provider, rate_per_sec=5,
        )

        # N-1 sleeps of 1/rate seconds
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list == [call(0.2), call(0.2)]

    @patch('src.mailer.get_suppressed_emails')
    def test_dry_run_sends_nothing(self, mock_suppressed, capsys):
        mock_suppressed.return_value = set()
        provider = _FakeProvider()

        stats = send_mailing(
            'My Subject', '<p>x</p>',
            recipients=['a@x.com', 'b@x.com', 'c@x.com'],
            provider=provider, dry_run=True,
        )

        assert provider.sent == []
        assert stats['sent'] == 0
        out = capsys.readouterr().out
        assert 'a@x.com, b@x.com' in out
        assert 'My Subject' in out
        assert '3 recipient(s)' in out

    @patch('src.mailer.get_suppressed_emails')
    def test_provider_failure_counted_not_fatal(self, mock_suppressed):
        mock_suppressed.return_value = set()
        provider = MagicMock(spec=EmailProvider)
        provider.send.side_effect = [MailerError('boom'), 'msg-2']

        stats = send_mailing(
            'S', '<p>x</p>',
            recipients=['a@x.com', 'b@x.com'],
            provider=provider, rate_per_sec=0,
        )
        assert stats['failed'] == 1
        assert stats['sent'] == 1


# === Email template ===

class TestEmailTemplate:
    def test_contains_body_unsubscribe_and_brand(self):
        html = render_email(
            '<h2>Play this week</h2>',
            unsubscribe_url='https://unsub.example.com?e=a%40x.com&t=deadbeef',
            title='Weekly',
            date=datetime(2026, 7, 13, tzinfo=timezone.utc),
        )
        assert '<h2>Play this week</h2>' in html
        assert 'https://unsub.example.com?e=a%40x.com&t=deadbeef' in html
        assert 'THIS WEEK IN' in html
        assert 'MOBILE GAMING' in html
        assert 'July 13, 2026' in html
        assert '#090a12' in html
        assert '#0fecff' in html
        assert 'max-width:600px' in html
        assert PHYSICAL_ADDRESS_PLACEHOLDER in html
        assert 'Unsubscribe' in html

    def test_links_get_accent_color_inline(self):
        html = render_email(
            '<a href="https://example.com/story">Story</a>',
            unsubscribe_url='https://u',
        )
        assert '<a style="color:#0fecff;" href="https://example.com/story">' in html


# === mailed.json log ===

class TestMailedLog:
    def test_record_and_load(self, tmp_path):
        log = tmp_path / 'mailed.json'
        assert load_mailed_ids(log) == []
        record_mailed_id(101, log)
        record_mailed_id(202, log)
        record_mailed_id(101, log)  # dedupe
        assert load_mailed_ids(log) == [101, 202]

    def test_corrupt_log_treated_as_empty(self, tmp_path):
        log = tmp_path / 'mailed.json'
        log.write_text('not json', encoding='utf-8')
        assert load_mailed_ids(log) == []


# === run_weekly_mailing (publish-gates-mailing) ===

def _published_article(article_id=555, days_ago=1, title='This Week — July 13, 2026'):
    published = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        'id': article_id,
        'title': title,
        'published_at': published.isoformat(),
        'body_html': '<p>digest body</p>',
    }


class TestRunWeeklyMailing:
    @patch('src.mailer.send_mailing')
    @patch('src.mailer.get_latest_published_article')
    def test_sends_and_records(self, mock_latest, mock_send, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, 'DATABASE_FULL_PATH', tmp_path / 'articles.db')
        mock_latest.return_value = _published_article(article_id=555)
        mock_send.return_value = {'recipients': 3, 'suppressed': 0, 'sent': 3, 'failed': 0}

        stats = run_weekly_mailing(dry_run=False)

        assert stats['sent'] == 3
        assert mock_send.call_args[1]['subject'] == 'This Week — July 13, 2026'
        assert mock_send.call_args[1]['article_html'] == '<p>digest body</p>'
        assert load_mailed_ids(tmp_path / 'mailed.json') == [555]

    @patch('src.mailer.send_mailing')
    @patch('src.mailer.get_latest_published_article')
    def test_already_mailed_id_skipped(self, mock_latest, mock_send, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, 'DATABASE_FULL_PATH', tmp_path / 'articles.db')
        record_mailed_id(555, tmp_path / 'mailed.json')
        mock_latest.return_value = _published_article(article_id=555)

        stats = run_weekly_mailing(dry_run=False)

        assert stats['sent'] == 0
        mock_send.assert_not_called()

    @patch('src.mailer.send_mailing')
    @patch('src.mailer.get_latest_published_article')
    def test_stale_article_skipped(self, mock_latest, mock_send, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, 'DATABASE_FULL_PATH', tmp_path / 'articles.db')
        mock_latest.return_value = _published_article(days_ago=10)

        stats = run_weekly_mailing(dry_run=False)

        assert stats['sent'] == 0
        mock_send.assert_not_called()

    @patch('src.mailer.send_mailing')
    @patch('src.mailer.get_latest_published_article')
    def test_no_published_article_is_noop(self, mock_latest, mock_send, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, 'DATABASE_FULL_PATH', tmp_path / 'articles.db')
        mock_latest.return_value = None

        stats = run_weekly_mailing(dry_run=False)
        assert stats == {'recipients': 0, 'suppressed': 0, 'sent': 0, 'failed': 0}
        mock_send.assert_not_called()

    @patch('src.mailer.send_mailing')
    @patch('src.mailer.get_latest_published_article')
    def test_dry_run_does_not_record(self, mock_latest, mock_send, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, 'DATABASE_FULL_PATH', tmp_path / 'articles.db')
        mock_latest.return_value = _published_article(article_id=777)
        mock_send.return_value = {'recipients': 3, 'suppressed': 0, 'sent': 0, 'failed': 0}

        run_weekly_mailing(dry_run=True)

        assert mock_send.call_args[1]['dry_run'] is True
        assert load_mailed_ids(tmp_path / 'mailed.json') == []


class TestGetLatestPublishedArticle:
    @patch('src.mailer.requests.get')
    @patch('src.shopify_publisher.get_blog_id')
    @patch('src.shopify_publisher.get_access_token')
    @patch('src.shopify_publisher._get_domain')
    def test_latest_published_fetch(self, mock_domain, mock_token, mock_blog, mock_get):
        from src.mailer import get_latest_published_article

        mock_domain.return_value = 'test.myshopify.com'
        mock_token.return_value = 'tok'
        mock_blog.return_value = 126947590478
        mock_get.return_value = _mock_response({'articles': [
            {'id': 1, 'title': 'Old', 'published_at': '2026-06-01T09:00:00Z'},
            {'id': 2, 'title': 'New', 'published_at': '2026-07-13T09:00:00Z'},
            {'id': 3, 'title': 'Draft', 'published_at': None},
        ]})

        article = get_latest_published_article()

        assert article['id'] == 2
        url = mock_get.call_args[0][0]
        assert 'blogs/126947590478/articles.json' in url
        assert mock_get.call_args[1]['params']['published_status'] == 'published'
