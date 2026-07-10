"""
Email-safe layout for the weekly digest mailing.

Wraps the digest article HTML in a table-based, inline-CSS-only layout
(max-width 600px) with the SwipePads dark brand:
  background #090a12, text #f5f6fc, links/accents #0fecff

Header: "THIS WEEK IN MOBILE GAMING" + date line.
Footer: physical address placeholder + personalized Unsubscribe link.
"""

from datetime import datetime, timezone

# Brand palette (email)
BG_COLOR = "#090a12"
CARD_COLOR = "#1a1a25"
TEXT_COLOR = "#f5f6fc"
TEXT_DIM_COLOR = "#9aa0b0"
ACCENT_COLOR = "#0fecff"

# CAN-SPAM requires a valid physical postal address in the footer.
# Replace before the first real send.
PHYSICAL_ADDRESS_PLACEHOLDER = "Outplay sp. z o.o., [street address], [city, country]"

EMAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0; padding:0; background-color:{bg}; -webkit-text-size-adjust:100%;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{bg};">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%;">

          <!-- Header -->
          <tr>
            <td style="padding:28px 24px 20px 24px; text-align:left;">
              <div style="font-family:Arial,Helvetica,sans-serif; font-size:13px; font-weight:bold; letter-spacing:4px; color:{accent}; text-transform:uppercase;">THIS WEEK IN</div>
              <div style="font-family:Arial,Helvetica,sans-serif; font-size:30px; font-weight:bold; color:{text}; letter-spacing:1px; padding-top:4px;">MOBILE GAMING</div>
              <div style="font-family:Arial,Helvetica,sans-serif; font-size:14px; color:{text_dim}; padding-top:8px;">{date_line}</div>
            </td>
          </tr>

          <!-- Body: digest article HTML -->
          <tr>
            <td style="padding:24px; background-color:{card}; border-radius:12px; font-family:Arial,Helvetica,sans-serif; font-size:15px; line-height:1.6; color:{text};">
              <style>
                /* Fallback for clients that honor embedded styles; layout does not depend on it */
                a {{ color: {accent}; }}
              </style>
              <div style="color:{text};">
{body_html}
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 24px; text-align:center; font-family:Arial,Helvetica,sans-serif; font-size:12px; line-height:1.6; color:{text_dim};">
              <p style="margin:0 0 8px 0;">You're receiving this because you subscribed to SwipePads updates.</p>
              <p style="margin:0 0 8px 0;">{physical_address}</p>
              <p style="margin:0;">
                <a href="{unsubscribe_url}" style="color:{accent}; text-decoration:underline;">Unsubscribe</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_email(
    body_html: str,
    unsubscribe_url: str,
    title: str = "This Week in Mobile Gaming",
    date: datetime = None,
) -> str:
    """
    Wrap digest article HTML in the email-safe branded layout.

    Args:
        body_html: The digest article HTML (as published on the blog)
        unsubscribe_url: Personalized unsubscribe URL for this recipient
        title: Email/document title
        date: Date for the header line (defaults to today, UTC)

    Returns:
        Complete HTML email document (inline CSS only, max-width 600px).
    """
    if date is None:
        date = datetime.now(timezone.utc)
    date_line = f"{date:%B} {date.day}, {date.year}"

    # Make bare links readable on the dark card: inject the accent color into
    # <a> tags that carry no inline style (email clients ignore <style> blocks).
    styled_body = body_html.replace(
        '<a href=', f'<a style="color:{ACCENT_COLOR};" href='
    )

    return EMAIL_TEMPLATE.format(
        title=title,
        bg=BG_COLOR,
        card=CARD_COLOR,
        text=TEXT_COLOR,
        text_dim=TEXT_DIM_COLOR,
        accent=ACCENT_COLOR,
        date_line=date_line,
        body_html=styled_body,
        physical_address=PHYSICAL_ADDRESS_PLACEHOLDER,
        unsubscribe_url=unsubscribe_url,
    )
