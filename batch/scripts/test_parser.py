"""Test the parser with the saved HTML file."""
from scrapers.judiciary.parsers import parse_judgment_html

# Read the saved HTML
with open("/Users/gdaley/CascadeProjects/Legal-AI/batch/judiciary_detail_page.html", "r", encoding="utf-8") as f:
    html = f.read()

print(f"HTML length: {len(html)}")

# Parse it
result = parse_judgment_html(html, "https://test.com")

print(f"\nParsed result:")
print(f"  case_number: {result.case_number}")
print(f"  case_name: {result.case_name}")
print(f"  neutral_citation: {result.neutral_citation}")
print(f"  court: {result.court}")
print(f"  decision_date: {result.decision_date}")
print(f"  judges: {result.judges}")
print(f"  parties: {result.parties}")
print(f"  word_count: {result.word_count}")
print(f"  language: {result.language}")
