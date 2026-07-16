# tests/test_extractor.py
# Manual test — run with: python tests/test_extractor.py

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from agent.scanner import scan_stale_pages
from agent.extractor import extract_page_content

# Get stale pages from scanner
pages = scan_stale_pages()

if not pages:
    print("No stale pages found — lower STALE_THRESHOLD_DAYS in .env")
else:
    # Test extractor on first 3 pages
    for page in pages[:3]:
        print(f"\n{'='*60}")
        print(f"PATH: {page['path']}")
        result = extract_page_content(page["path"])
        print(f"TITLE:         {result.get('title')}")
        print(f"DESCRIPTION:   {result.get('description')}")
        print(f"LAST MODIFIED: {result.get('last_modified')}")
        print(f"TEMPLATE:      {result.get('template')}")
        print(f"TEXT COMPONENTS ({len(result.get('text_components', []))}):")
        for t in result.get("text_components", []):
            print(f"  → {t[:100]}...")