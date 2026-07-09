"""
Weekly digest cover image generator — branded 1200x630 featured image
for the Shopify blog article (attached base64 in the article POST).

Brand style:
  background #090a12, accent cyan #0fecff, card #1a1a25
  "THIS WEEK IN" (small, cyan, uppercase, letter-spaced)
  "MOBILE GAMING" (large, bold)
  date line + up to 3 topic tags as pill-shaped outlines

Self-contained: uses fonts bundled with Pillow / present on the OS —
never downloads fonts at runtime.

Output: data/digests/YYYY-MM-DD-cover.png
"""

import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from src.config import Config

logger = logging.getLogger(__name__)

# Canvas
COVER_WIDTH = 1200
COVER_HEIGHT = 630

# Brand palette
COLOR_BACKGROUND = "#090a12"
COLOR_ACCENT = "#0fecff"
COLOR_CARD = "#1a1a25"
COLOR_TEXT = "#f2f3f7"
COLOR_TEXT_DIM = "#9aa0b0"

MAX_TAGS = 3

# Font candidates, tried in order. DejaVu Sans Bold ships with Pillow on many
# distros / with matplotlib; Arial covers Windows. NO runtime downloads.
_FONT_CANDIDATES_BOLD = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"]
_FONT_CANDIDATES_REGULAR = ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]


class CoverImageError(Exception):
    """Base exception for cover image generation errors."""
    pass


def _load_font(size: int, bold: bool = True):
    """Load the best available font at the given size (self-contained)."""
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    # Pillow >= 10.1: scalable built-in default font
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple:
    """Measure text (width, height)."""
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _draw_spaced_text(
    draw: ImageDraw.ImageDraw, xy: tuple, text: str, font, fill, spacing: int
) -> int:
    """Draw text with extra letter-spacing; return total width drawn."""
    x, y = xy
    start_x = x
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        char_width, _ = _text_size(draw, char, font)
        x += char_width + spacing
    return x - start_x - spacing


_TAG_SPLIT = re.compile(r'\s*(?:—|–|:|\||\s-\s)\s*')


def extract_topic_tags(articles: List[dict], max_tags: int = MAX_TAGS) -> List[str]:
    """
    Derive short topic tags from top stories' titles.

    Takes the leading phrase of each title (before the first delimiter),
    truncated and uppercased — good enough for cover pills.
    """
    tags = []
    for article in articles:
        title = (article.get('title') or '').strip()
        if not title:
            continue
        lead = _TAG_SPLIT.split(title)[0].strip()
        if not lead:
            continue
        if len(lead) > 22:
            lead = lead[:22].rstrip() + '…'
        tag = lead.upper()
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= max_tags:
            break
    return tags


def generate_cover_image(
    date: datetime = None,
    tags: List[str] = None,
    output_dir: Path = None,
) -> Path:
    """
    Render the branded weekly cover image (1200x630 PNG).

    Args:
        date: Digest date (defaults to today, UTC)
        tags: Up to 3 short topic tags (pill outlines); extra tags are dropped
        output_dir: Defaults to data/digests

    Returns:
        Path to the saved PNG (data/digests/YYYY-MM-DD-cover.png).
    """
    if date is None:
        date = datetime.now(timezone.utc)
    tags = [t for t in (tags or []) if t][:MAX_TAGS]
    if output_dir is None:
        output_dir = Config.DATABASE_FULL_PATH.parent / 'digests'

    image = Image.new('RGB', (COVER_WIDTH, COVER_HEIGHT), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Card panel
    card_margin = 56
    draw.rounded_rectangle(
        (card_margin, card_margin, COVER_WIDTH - card_margin, COVER_HEIGHT - card_margin),
        radius=28,
        fill=COLOR_CARD,
        outline=COLOR_ACCENT,
        width=2,
    )

    left = card_margin + 64
    y = card_margin + 88

    # Kicker: THIS WEEK IN — small, cyan, uppercase, letter-spaced
    kicker_font = _load_font(30, bold=True)
    _draw_spaced_text(draw, (left, y), "THIS WEEK IN", kicker_font, COLOR_ACCENT, spacing=10)
    y += 66

    # Title: MOBILE GAMING — large bold
    title_font = _load_font(96, bold=True)
    draw.text((left, y), "MOBILE GAMING", font=title_font, fill=COLOR_TEXT)
    y += 128

    # Date line
    date_font = _load_font(34, bold=False)
    date_line = f"{date:%B} {date.day}, {date.year}"
    draw.text((left, y), date_line, font=date_font, fill=COLOR_TEXT_DIM)
    y += 88

    # Topic tags as pill-shaped outlines
    if tags:
        tag_font = _load_font(26, bold=True)
        pad_x, pad_y = 26, 14
        x = left
        for tag in tags:
            text_w, text_h = _text_size(draw, tag, tag_font)
            pill_w = text_w + pad_x * 2
            pill_h = text_h + pad_y * 2

            # Wrap to a second row if the pill would overflow the card
            if x + pill_w > COVER_WIDTH - card_margin - 64:
                x = left
                y += pill_h + 16

            draw.rounded_rectangle(
                (x, y, x + pill_w, y + pill_h),
                radius=pill_h // 2,
                outline=COLOR_ACCENT,
                width=2,
            )
            draw.text(
                (x + pad_x, y + pad_y - 2), tag, font=tag_font, fill=COLOR_TEXT
            )
            x += pill_w + 20

    # Save
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date.strftime('%Y-%m-%d')}-cover.png"
    output_path = output_dir / filename
    image.save(output_path, format='PNG')

    logger.info(f"Cover image saved: {output_path} ({COVER_WIDTH}x{COVER_HEIGHT})")
    return output_path


def find_cover_for_digest(digest_path: Path) -> Optional[Path]:
    """Find the cover PNG matching a digest HTML file (same date stem)."""
    digest_path = Path(digest_path)
    if not digest_path.name.endswith('-digest.html'):
        return None
    cover = digest_path.with_name(
        digest_path.name.replace('-digest.html', '-cover.png')
    )
    return cover if cover.exists() else None
