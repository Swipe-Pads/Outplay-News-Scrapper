"""
Image downloader module with validation and retry logic.

This module provides functionality to download images from URLs, validate them,
and save them to a local directory with safe filenames.
"""

import os
import re
import time
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote
import requests
from PIL import Image
from io import BytesIO


class ImageDownloadError(Exception):
    """Base exception for image download errors."""
    pass


class ImageValidationError(ImageDownloadError):
    """Exception raised when image validation fails."""
    pass


class NetworkError(ImageDownloadError):
    """Exception raised for network-related errors."""
    pass


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to be safe for filesystem usage.

    Args:
        filename: The original filename to sanitize
        max_length: Maximum length for the filename (default: 255)

    Returns:
        A safe filename string
    """
    # Remove path separators and dangerous characters
    safe_chars = re.sub(r'[^\w\s\-\.]', '_', filename)

    # Remove leading/trailing dots and spaces
    safe_chars = safe_chars.strip('. ')

    # Replace multiple spaces/underscores with single underscore
    safe_chars = re.sub(r'[\s_]+', '_', safe_chars)

    # Ensure we have a filename
    if not safe_chars:
        safe_chars = 'unnamed'

    # Truncate to max_length while preserving extension
    if len(safe_chars) > max_length:
        name, ext = os.path.splitext(safe_chars)
        name = name[:max_length - len(ext)]
        safe_chars = name + ext

    return safe_chars


def generate_unique_filename(base_path: Path, filename: str) -> Path:
    """
    Generate a unique filename by appending a counter if file exists.

    Args:
        base_path: Directory path where file will be saved
        filename: Desired filename

    Returns:
        Path object with unique filename
    """
    filepath = base_path / filename

    if not filepath.exists():
        return filepath

    name, ext = os.path.splitext(filename)
    counter = 1

    while True:
        new_filename = f"{name}_{counter}{ext}"
        filepath = base_path / new_filename
        if not filepath.exists():
            return filepath
        counter += 1


def extract_filename_from_url(url: str) -> str:
    """
    Extract filename from URL.

    Args:
        url: The URL to extract filename from

    Returns:
        Extracted filename or generated fallback
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)

    # Get the last part of the path
    filename = os.path.basename(path)

    # If no filename or no extension, generate one based on URL hash
    if not filename or '.' not in filename:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"image_{url_hash}.jpg"

    return filename


def validate_image(image_data: bytes) -> Tuple[bool, Optional[str]]:
    """
    Validate that the data is a valid image file.

    Args:
        image_data: Raw image bytes to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if data is empty
    if not image_data or len(image_data) == 0:
        return False, "Image data is empty"

    # Check minimum size (at least 100 bytes for any valid image)
    if len(image_data) < 100:
        return False, f"Image data too small ({len(image_data)} bytes)"

    try:
        # Try to open and verify the image with PIL
        img = Image.open(BytesIO(image_data))
        img.verify()

        # Re-open to check dimensions (verify() closes the file)
        img = Image.open(BytesIO(image_data))
        width, height = img.size

        if width == 0 or height == 0:
            return False, "Image has zero dimensions"

        # Check if image format is supported
        if img.format not in ['JPEG', 'PNG', 'GIF', 'BMP', 'WEBP', 'TIFF']:
            return False, f"Unsupported image format: {img.format}"

        return True, None

    except Exception as e:
        return False, f"Image validation failed: {str(e)}"


def download_image(
    url: str,
    output_dir: str = "images",
    max_retries: int = 3,
    retry_delay: float = 1.0,
    timeout: int = 30
) -> str:
    """
    Download an image from a URL with validation and retry logic.

    Args:
        url: The URL of the image to download
        output_dir: Directory to save the image (default: "images")
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay in seconds between retries (default: 1.0)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Path to the downloaded image file (as string)

    Raises:
        ImageDownloadError: If download fails after all retries
        ImageValidationError: If downloaded file is not a valid image
        NetworkError: If network-related errors occur
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Extract and sanitize filename
    raw_filename = extract_filename_from_url(url)
    safe_filename = sanitize_filename(raw_filename)

    last_error = None

    for attempt in range(max_retries):
        try:
            # Download the image
            response = requests.get(
                url,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; ImageDownloader/1.0)'}
            )
            response.raise_for_status()

            # Get the image data
            image_data = response.content

            # Validate the image
            is_valid, error_msg = validate_image(image_data)
            if not is_valid:
                raise ImageValidationError(f"Invalid image: {error_msg}")

            # Generate unique filename if needed
            output_file = generate_unique_filename(output_path, safe_filename)

            # Save the image
            with open(output_file, 'wb') as f:
                f.write(image_data)

            # Final verification: try to open the saved file
            try:
                with Image.open(output_file) as img:
                    img.verify()
            except Exception as e:
                output_file.unlink(missing_ok=True)
                raise ImageValidationError(f"Saved image verification failed: {str(e)}")

            return str(output_file)

        except requests.exceptions.Timeout as e:
            last_error = NetworkError(f"Request timeout: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            last_error = NetworkError(f"Connection error: {str(e)}")
        except requests.exceptions.HTTPError as e:
            # Don't retry on 4xx errors (client errors)
            if 400 <= response.status_code < 500:
                raise ImageDownloadError(f"HTTP {response.status_code}: {str(e)}")
            last_error = NetworkError(f"HTTP error: {str(e)}")
        except requests.exceptions.RequestException as e:
            last_error = NetworkError(f"Request error: {str(e)}")
        except ImageValidationError as e:
            # Don't retry validation errors
            raise
        except Exception as e:
            last_error = ImageDownloadError(f"Unexpected error: {str(e)}")

        # If this wasn't the last attempt, wait before retrying
        if attempt < max_retries - 1:
            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

    # All retries exhausted
    raise last_error or ImageDownloadError(f"Failed to download image after {max_retries} attempts")


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python image_downloader.py <image_url>")
        sys.exit(1)

    try:
        image_url = sys.argv[1]
        local_path = download_image(image_url)
        print(f"Image successfully downloaded to: {local_path}")
    except ImageDownloadError as e:
        print(f"Error: {e}")
        sys.exit(1)
