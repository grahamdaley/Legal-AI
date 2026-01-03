"""Explore eLegislation website structure."""
import asyncio
from playwright.async_api import async_playwright


async def explore():
    """Fetch and analyze eLegislation page."""
    url = "https://www.elegislation.gov.hk/hk/cap1"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        
        print(f"Fetching: {url}")
        await page.goto(url, wait_until="networkidle", timeout=90000)
        await asyncio.sleep(5)  # Wait for JS to load
        
        content = await page.content()
        print(f"Content length: {len(content)}")
        print(f"Page title: {await page.title()}")
        
        # Save for inspection
        with open("/Users/gdaley/CascadeProjects/Legal-AI/batch/elegislation_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Saved to elegislation_page.html")
        
        # Check for common selectors
        selectors = [
            ".legislation-content",
            ".cap-content", 
            "#content",
            ".content",
            "main",
            "article",
            ".body-content",
            "#mainContent",
        ]
        
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    print(f"  Found: {sel}")
            except:
                pass
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(explore())
