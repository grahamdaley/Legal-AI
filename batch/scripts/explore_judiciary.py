#!/usr/bin/env python3
"""
Script to explore the Judiciary website structure.
Run this to understand the HTML structure for scraping.
"""

import asyncio
from playwright.async_api import async_playwright


async def explore_search_results():
    """Fetch and analyze the search results page."""
    # First visit the main site to establish session
    base_url = "https://legalref.judiciary.hk/lrs/common/ju/judgment.jsp"
    
    search_url = (
        "https://legalref.judiciary.hk/lrs/common/search/search_result_form.jsp?"
        "isadvsearch=1&txtselectopt=1&txtSearch=&txtselectopt1=2&txtSearch1=&"
        "txtselectopt2=3&txtSearch2=&stem=1&txtselectopt3=5&"
        "txtSearch3=11%2F3%2F1998&day1=11&month=3&year=1998&"
        "txtselectopt4=6&txtSearch4=&txtselectopt5=7&txtSearch5=&"
        "txtselectopt6=8&txtSearch6=&txtselectopt7=9&txtSearch7=&"
        "selallct=1&selSchct=FA&selSchct=CA&selSchct=HC&selSchct=CT&"
        "selSchct=DC&selSchct=FC&selSchct=LD&selSchct=OT&"
        "selcourtname=&selcourtype=&txtselectopt8=10&txtSearch8=&"
        "txtselectopt9=4&txtSearch9=&txtselectopt10=12&txtSearch10=&"
        "selall2=1&selDatabase2=JU&selDatabase2=RV&selDatabase2=RS&"
        "selDatabase2=PD&order=1&SHC=&page=1"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # First visit the main page to establish session/cookies
        print("Visiting main site first to establish session...")
        await page.goto(base_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        
        print(f"Main page title: {await page.title()}")
        
        # Now visit the search results
        print(f"\nFetching search results: {search_url[:80]}...")
        await page.goto(search_url, wait_until="networkidle", timeout=60000)

        # Wait a bit for any JS to finish
        await asyncio.sleep(2)

        # Get page title
        title = await page.title()
        print(f"\nPage Title: {title}")

        # Get the HTML content
        html = await page.content()

        # Save full HTML for analysis
        with open("judiciary_search_results.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nSaved full HTML to judiciary_search_results.html ({len(html)} bytes)")

        # Find all links
        links = await page.query_selector_all("a[href]")
        print(f"\nFound {len(links)} links on page")

        # Look for judgment links
        judgment_links = []
        pagination_links = []

        for link in links:
            href = await link.get_attribute("href")
            text = await link.inner_text()

            if href:
                # Check for judgment links
                if "ju_frame" in href.lower() or "judgment" in href.lower():
                    judgment_links.append((href, text.strip()[:80]))
                # Check for pagination
                elif "page=" in href.lower():
                    pagination_links.append((href, text.strip()))

        print(f"\n=== JUDGMENT LINKS ({len(judgment_links)}) ===")
        for href, text in judgment_links[:10]:
            print(f"  {text}: {href[:100]}")

        print(f"\n=== PAGINATION LINKS ({len(pagination_links)}) ===")
        for href, text in pagination_links[:10]:
            print(f"  Page {text}: {href[:80]}...")

        # Look for table rows that might contain results
        rows = await page.query_selector_all("tr")
        print(f"\n=== TABLE ROWS ({len(rows)}) ===")

        # Try to find the results table
        tables = await page.query_selector_all("table")
        print(f"Found {len(tables)} tables")

        # Look for specific patterns in the HTML
        if "No record found" in html:
            print("\n*** NO RECORDS FOUND for this date ***")
        
        # Count how many times certain patterns appear
        import re
        case_patterns = [
            (r"\[(\d{4})\]\s*(HKCFA|HKCA|HKCFI|HKDC|HKFC)", "Neutral citations"),
            (r"(FACV|CACV|HCAL|HCMP|DCCC|FCMC)\s*\d+/\d{4}", "Case numbers"),
            (r"ju_frame\.jsp", "Judgment frame links"),
        ]

        print("\n=== PATTERN MATCHES ===")
        for pattern, name in case_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            print(f"  {name}: {len(matches)} matches")
            if matches[:3]:
                print(f"    Examples: {matches[:3]}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(explore_search_results())
