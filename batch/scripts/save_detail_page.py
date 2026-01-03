"""Save a judgment detail page for analysis."""
import asyncio
from playwright.async_api import async_playwright


async def save_detail_page():
    """Fetch and save a judgment detail page."""
    # First visit main site to establish session
    base_url = "https://legalref.judiciary.hk/lrs/common/ju/judgment.jsp"
    # The frame page loads content from search_result_detail_body.jsp
    detail_url = "https://legalref.judiciary.hk/lrs/common/search/search_result_detail_body.jsp?DIS=32205&QS=%2B&TP=JU"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        
        # Establish session
        print("Visiting main site first...")
        await page.goto(base_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        
        # Now fetch detail page
        print(f"Fetching detail page: {detail_url}")
        await page.goto(detail_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        
        content = await page.content()
        print(f"Page title: {await page.title()}")
        print(f"Content length: {len(content)}")
        
        # Save HTML
        with open("judiciary_detail_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Saved to judiciary_detail_page.html")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(save_detail_page())
