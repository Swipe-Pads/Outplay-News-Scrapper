"""Tests for src/image_downloader.py"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO

from src.image_downloader import (
    sanitize_filename,
    generate_unique_filename,
    extract_filename_from_url,
    validate_image,
    download_image,
    ImageDownloadError,
    ImageValidationError,
    NetworkError,
)


# --- Helper: create a minimal valid PNG ---
def _make_png_bytes(width=100, height=100):
    """Create a valid PNG image with enough bytes to pass validation."""
    from PIL import Image
    img = Image.new('RGB', (width, height), color='red')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


# === sanitize_filename ===

class TestSanitizeFilename:
    def test_basic(self):
        assert sanitize_filename("hello.jpg") == "hello.jpg"

    def test_removes_dangerous_chars(self):
        result = sanitize_filename("he<ll>o:w*or?ld.jpg")
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result

    def test_strips_dots_and_spaces(self):
        result = sanitize_filename("...test.jpg...")
        assert not result.startswith('.')
        assert not result.endswith('.')

    def test_collapses_underscores(self):
        result = sanitize_filename("a   b___c.jpg")
        assert "  " not in result
        assert "___" not in result

    def test_empty_becomes_unnamed(self):
        assert sanitize_filename("") == "unnamed"

    def test_special_chars_only(self):
        result = sanitize_filename("!!!")
        assert result  # not empty

    def test_truncation_preserves_extension(self):
        long_name = "a" * 300 + ".jpg"
        result = sanitize_filename(long_name, max_length=20)
        assert len(result) <= 20
        assert result.endswith(".jpg")


# === generate_unique_filename ===

class TestGenerateUniqueFilename:
    def test_returns_original_if_no_conflict(self, tmp_path):
        result = generate_unique_filename(tmp_path, "test.jpg")
        assert result == tmp_path / "test.jpg"

    def test_appends_counter_on_conflict(self, tmp_path):
        (tmp_path / "test.jpg").write_bytes(b"x")
        result = generate_unique_filename(tmp_path, "test.jpg")
        assert result == tmp_path / "test_1.jpg"

    def test_increments_counter(self, tmp_path):
        (tmp_path / "test.jpg").write_bytes(b"x")
        (tmp_path / "test_1.jpg").write_bytes(b"x")
        result = generate_unique_filename(tmp_path, "test.jpg")
        assert result == tmp_path / "test_2.jpg"


# === extract_filename_from_url ===

class TestExtractFilenameFromUrl:
    def test_simple_url(self):
        result = extract_filename_from_url("https://example.com/images/photo.jpg")
        assert result == "photo.jpg"

    def test_no_extension_generates_fallback(self):
        result = extract_filename_from_url("https://example.com/images/photo")
        assert result.startswith("image_")
        assert result.endswith(".jpg")

    def test_url_encoded_filename(self):
        result = extract_filename_from_url("https://example.com/my%20photo.jpg")
        assert "photo" in result

    def test_empty_path_generates_fallback(self):
        result = extract_filename_from_url("https://example.com/")
        assert result.startswith("image_")


# === validate_image ===

class TestValidateImage:
    def test_valid_png(self):
        data = _make_png_bytes()
        is_valid, error = validate_image(data)
        assert is_valid is True
        assert error is None

    def test_empty_data(self):
        is_valid, error = validate_image(b"")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_too_small(self):
        is_valid, error = validate_image(b"x" * 50)
        assert is_valid is False
        assert "small" in error.lower()

    def test_not_an_image(self):
        is_valid, error = validate_image(b"x" * 200)
        assert is_valid is False

    def test_none_data(self):
        is_valid, error = validate_image(None)
        assert is_valid is False


# === download_image ===

class TestDownloadImage:
    @patch('src.image_downloader.requests.get')
    def test_successful_download(self, mock_get, tmp_path):
        png_data = _make_png_bytes()
        mock_response = MagicMock()
        mock_response.content = png_data
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        output_dir = str(tmp_path / "images")
        result = download_image(
            "https://example.com/photo.png",
            output_dir=output_dir
        )

        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

    @patch('src.image_downloader.requests.get')
    def test_retries_on_timeout(self, mock_get, tmp_path):
        import requests as req
        png_data = _make_png_bytes()

        mock_response = MagicMock()
        mock_response.content = png_data
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_get.side_effect = [
            req.exceptions.Timeout("timeout"),
            mock_response,
        ]

        result = download_image(
            "https://example.com/photo.png",
            output_dir=str(tmp_path),
            max_retries=3,
            retry_delay=0.01,
        )
        assert Path(result).exists()
        assert mock_get.call_count == 2

    @patch('src.image_downloader.requests.get')
    def test_raises_after_max_retries(self, mock_get, tmp_path):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("timeout")

        with pytest.raises(NetworkError, match="timeout"):
            download_image(
                "https://example.com/photo.png",
                output_dir=str(tmp_path),
                max_retries=2,
                retry_delay=0.01,
            )
        assert mock_get.call_count == 2

    @patch('src.image_downloader.requests.get')
    def test_no_retry_on_4xx(self, mock_get, tmp_path):
        import requests as req
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(ImageDownloadError, match="404"):
            download_image(
                "https://example.com/missing.jpg",
                output_dir=str(tmp_path),
                max_retries=3,
                retry_delay=0.01,
            )
        assert mock_get.call_count == 1

    @patch('src.image_downloader.requests.get')
    def test_no_retry_on_validation_error(self, mock_get, tmp_path):
        mock_response = MagicMock()
        mock_response.content = b"not an image" * 20
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with pytest.raises(ImageValidationError):
            download_image(
                "https://example.com/bad.jpg",
                output_dir=str(tmp_path),
                max_retries=3,
                retry_delay=0.01,
            )
        assert mock_get.call_count == 1

    def test_default_output_dir_is_project_relative(self):
        """Ensure default output_dir resolves to project root/images."""
        from src.image_downloader import download_image
        import inspect
        src = inspect.getsource(download_image)
        assert "Path(__file__).parent.parent" in src
