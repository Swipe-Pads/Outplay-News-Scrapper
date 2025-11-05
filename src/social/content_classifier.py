"""
Content type classification for social media posts.
Detects different content types: text, images, videos, YouTube, etc.
"""

import re
from typing import Dict, List
from bs4 import BeautifulSoup, Tag


# Post type constants
POST_TYPE_TEXT = "text"
POST_TYPE_TEXT_IMAGE = "text_image"
POST_TYPE_TEXT_IMAGES = "text_images"
POST_TYPE_TEXT_VIDEO = "text_video"
POST_TYPE_TEXT_YOUTUBE = "text_youtube"
POST_TYPE_TEXT_LINK = "text_link"
POST_TYPE_REPOST = "repost"


def classify_post_type(post_element: Tag, content: str) -> str:
    """
    Classify the type of a social media post.

    Args:
        post_element: BeautifulSoup element containing the post
        content: Text content of the post

    Returns:
        Post type string (e.g., 'text', 'text_image', 'text_video')
    """
    # Check for video
    if has_video(post_element):
        return POST_TYPE_TEXT_VIDEO

    # Check for YouTube link
    if has_youtube_link(content) or has_youtube_embed(post_element):
        return POST_TYPE_TEXT_YOUTUBE

    # Check for images
    image_count = count_images(post_element)
    if image_count > 1:
        return POST_TYPE_TEXT_IMAGES
    elif image_count == 1:
        return POST_TYPE_TEXT_IMAGE

    # Check for link preview
    if has_link_preview(post_element):
        return POST_TYPE_TEXT_LINK

    # Default to text-only
    return POST_TYPE_TEXT


def has_video(element: Tag) -> bool:
    """
    Check if post contains a video.

    Args:
        element: BeautifulSoup element

    Returns:
        True if video found
    """
    # Twitter video indicators
    if element.find('div', {'data-testid': 'videoPlayer'}):
        return True

    # Generic video tag
    if element.find('video'):
        return True

    return False


def has_youtube_link(content: str) -> bool:
    """
    Check if post content contains a YouTube link.

    Args:
        content: Text content of post

    Returns:
        True if YouTube link found
    """
    youtube_patterns = [
        r'youtube\.com/watch\?v=',
        r'youtu\.be/',
        r'youtube\.com/embed/'
    ]

    for pattern in youtube_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return False


def has_youtube_embed(element: Tag) -> bool:
    """
    Check if post has YouTube embed/preview.

    Args:
        element: BeautifulSoup element

    Returns:
        True if YouTube embed found
    """
    # Check for YouTube iframe
    iframe = element.find('iframe')
    if iframe and 'youtube' in str(iframe.get('src', '')):
        return True

    # Check for YouTube preview card (Twitter)
    card = element.find('div', {'data-testid': 'card.wrapper'})
    if card:
        link = card.find('a', href=True)
        if link and 'youtube' in link['href']:
            return True

    return False


def count_images(element: Tag) -> int:
    """
    Count images in a post.

    Args:
        element: BeautifulSoup element

    Returns:
        Number of images found
    """
    # Twitter photo indicators
    photo_divs = element.find_all('div', {'data-testid': 'tweetPhoto'})
    if photo_divs:
        # Count img tags within photo containers
        total_images = 0
        for photo_div in photo_divs:
            images = photo_div.find_all('img')
            total_images += len(images)
        return total_images

    # Generic img tags (excluding profile pictures, icons)
    images = element.find_all('img')
    # Filter out small images (likely icons/avatars)
    content_images = [
        img for img in images
        if not _is_icon_image(img)
    ]
    return len(content_images)


def _is_icon_image(img: Tag) -> bool:
    """Check if an image is likely an icon/avatar (small)."""
    # Check for small dimensions in style or attributes
    style = img.get('style', '')
    if 'width: 20px' in style or 'width:20px' in style:
        return True
    if 'width: 40px' in style or 'width:40px' in style:
        return True

    # Check class names
    classes = img.get('class', [])
    icon_indicators = ['avatar', 'icon', 'emoji', 'badge']
    for cls in classes:
        if any(indicator in str(cls).lower() for indicator in icon_indicators):
            return True

    return False


def has_link_preview(element: Tag) -> bool:
    """
    Check if post has a link preview card.

    Args:
        element: BeautifulSoup element

    Returns:
        True if link preview found
    """
    # Twitter card wrapper
    if element.find('div', {'data-testid': 'card.wrapper'}):
        return True

    # Facebook link preview (common class patterns)
    link_preview_patterns = [
        {'class_': lambda x: x and 'link-preview' in ' '.join(x)},
        {'class_': lambda x: x and 'attachment' in ' '.join(x)}
    ]

    for pattern in link_preview_patterns:
        if element.find('div', pattern):
            return True

    return False


def extract_youtube_id(content: str, element: Tag = None) -> str:
    """
    Extract YouTube video ID from content or element.

    Args:
        content: Text content
        element: BeautifulSoup element (optional)

    Returns:
        YouTube video ID or empty string if not found
    """
    # Pattern 1: youtube.com/watch?v=VIDEO_ID
    match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', content)
    if match:
        return match.group(1)

    # Pattern 2: youtu.be/VIDEO_ID
    match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', content)
    if match:
        return match.group(1)

    # Pattern 3: youtube.com/embed/VIDEO_ID
    match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', content)
    if match:
        return match.group(1)

    # Try element if provided
    if element:
        # Check iframe src
        iframe = element.find('iframe')
        if iframe and iframe.get('src'):
            src = iframe['src']
            match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', src)
            if match:
                return match.group(1)

        # Check link in card
        card = element.find('div', {'data-testid': 'card.wrapper'})
        if card:
            link = card.find('a', href=True)
            if link:
                return extract_youtube_id(link['href'])

    return ""


def extract_hashtags(content: str) -> List[str]:
    """
    Extract hashtags from post content.

    Args:
        content: Text content of post

    Returns:
        List of hashtags (without # symbol)
    """
    hashtags = re.findall(r'#(\w+)', content)
    return hashtags


def extract_mentions(content: str) -> List[str]:
    """
    Extract @mentions from post content.

    Args:
        content: Text content of post

    Returns:
        List of mentions (without @ symbol)
    """
    mentions = re.findall(r'@(\w+)', content)
    return mentions


def extract_media_urls(element: Tag, post_type: str) -> List[Dict[str, str]]:
    """
    Extract media URLs from a post element.

    Args:
        element: BeautifulSoup element
        post_type: Type of post (from classify_post_type)

    Returns:
        List of media dictionaries with 'type' and 'url' keys
    """
    media_list = []

    # Extract images
    if post_type in [POST_TYPE_TEXT_IMAGE, POST_TYPE_TEXT_IMAGES]:
        images = _extract_image_urls(element)
        media_list.extend([{'type': 'image', 'url': url} for url in images])

    # Extract video
    if post_type == POST_TYPE_TEXT_VIDEO:
        video_url = _extract_video_url(element)
        if video_url:
            media_list.append({'type': 'video', 'url': video_url})

    # Extract YouTube
    if post_type == POST_TYPE_TEXT_YOUTUBE:
        youtube_id = extract_youtube_id("", element)
        if youtube_id:
            media_list.append({
                'type': 'youtube',
                'url': f'https://www.youtube.com/watch?v={youtube_id}',
                'youtube_id': youtube_id
            })

    return media_list


def _extract_image_urls(element: Tag) -> List[str]:
    """Extract image URLs from element."""
    urls = []

    # Twitter photo containers
    photo_divs = element.find_all('div', {'data-testid': 'tweetPhoto'})
    for photo_div in photo_divs:
        images = photo_div.find_all('img')
        for img in images:
            src = img.get('src')
            if src and not _is_icon_image(img):
                urls.append(src)

    # Generic images if no Twitter-specific found
    if not urls:
        images = element.find_all('img')
        for img in images:
            src = img.get('src')
            if src and not _is_icon_image(img):
                urls.append(src)

    return urls


def _extract_video_url(element: Tag) -> str:
    """Extract video URL from element."""
    # Twitter video player
    video_div = element.find('div', {'data-testid': 'videoPlayer'})
    if video_div:
        video = video_div.find('video')
        if video and video.get('src'):
            return video['src']
        # Check source elements
        source = video_div.find('source') if video_div.find('video') else None
        if source and source.get('src'):
            return source['src']

    # Generic video tag
    video = element.find('video')
    if video:
        if video.get('src'):
            return video['src']
        source = video.find('source')
        if source and source.get('src'):
            return source['src']

    return ""
