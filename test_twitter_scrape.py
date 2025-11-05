"""
Test script to attempt live Twitter scraping.
This will help us understand the page structure and create test HTML files.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


async def scrape_twitter_page(url: str, output_file: str):
    """
    Attempt to scrape a Twitter page and save the HTML.

    Args:
        url: Twitter profile URL
        output_file: Path to save HTML output
    """
    print(f"🔍 Attempting to scrape: {url}")

    async with async_playwright() as p:
        try:
            # Launch browser
            print("  → Launching browser...")
            browser = await p.chromium.launch(headless=True)

            # Create context with realistic settings
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US'
            )

            # Create new page
            page = await context.new_page()

            # Navigate to URL
            print(f"  → Navigating to {url}...")
            response = await page.goto(url, wait_until='networkidle', timeout=30000)

            print(f"  → Response status: {response.status}")

            if response.status == 200:
                # Wait for tweets to load
                print("  → Waiting for content to load...")
                try:
                    await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
                    print("  → ✅ Tweets detected on page!")
                except:
                    print("  → ⚠️  No tweets found with standard selector, checking for login wall...")

                # Get page content
                html_content = await page.content()

                # Save to file
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(html_content, encoding='utf-8')

                print(f"  → ✅ Saved HTML to: {output_file}")
                print(f"  → HTML size: {len(html_content):,} bytes")

                # Take screenshot for debugging
                screenshot_path = output_path.with_suffix('.png')
                await page.screenshot(path=str(screenshot_path), full_page=False)
                print(f"  → 📸 Screenshot saved: {screenshot_path}")

                # Count tweets found
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                print(f"  → Found {len(tweets)} tweets on page")

                # Check for common elements
                title = await page.title()
                print(f"  → Page title: {title}")

            else:
                print(f"  → ❌ Failed with status code: {response.status}")

            await browser.close()

        except Exception as e:
            print(f"  → ❌ Error: {type(e).__name__}: {str(e)}")


async def main():
    """Test scraping Delta Force Twitter page."""
    print("="*60)
    print("Twitter Scraping Test - Delta Force")
    print("="*60)
    print()

    twitter_url = "https://x.com/DeltaForce_Game"
    output_file = "test_data/social/twitter_deltaforce_live.html"

    await scrape_twitter_page(twitter_url, output_file)

    print()
    print("="*60)
    print("Test complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
