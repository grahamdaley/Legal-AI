"""Test fetching a detail body page with session."""
import asyncio
from playwright.async_api import async_playwright


async def test_fetch():
    """Test fetching detail body with proper session."""
    base_url = "https://legalref.judiciary.hk/lrs/common/ju/judgment.jsp"
    detail_url = "https://legalref.judiciary.hk/lrs/common/search/search_result_detail_body.jsp?DIS=32205&QS=%2B&TP=JU"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        
        # Establish session first
        print("1. Visiting main site to establish session...")
        await page.goto(base_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        print(f"   Main page title: {await page.title()}")
        
        # Now fetch detail body
        print(f"\n2. Fetching detail body: {detail_url}")
        await page.goto(detail_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        
        content = await page.content()
        print(f"   Content length: {len(content)}")
        
        # Check for title
        title = await page.title()
        print(f"   Page title: '{title}'")
        
        # Check for key elements
        if "FACC" in content or "HKSAR" in content:
            print("   ✓ Found case content!")
        else:
            print("   ✗ No case content found")
            
        # Save for inspection
        with open("test_detail_body.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("\n   Saved to test_detail_body.html")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_fetch())
