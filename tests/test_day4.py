# tests/test_day4.py
# End-to-end test: page dict → QwQ-Plus reasoning → Qwen-Max refresh
# Run with: python tests/test_day4.py

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from agent.scanner import scan_stale_pages
from agent.extractor import extract_page_content
from agent.reasoner import analyze_staleness
from agent.generator import generate_refresh
from agent.llm.dashscope_client import DashScopeClient
import json

client = DashScopeClient()

# Get one stale page
pages = scan_stale_pages()
if not pages:
    print("No stale pages found — lower STALE_THRESHOLD_DAYS in .env")
    exit()

page = pages[0]
print(f"\n{'='*60}")
print(f"Testing on: {page['path']}")

# Step 1: Extract
print("\n[1] Extracting content...")
page_dict = extract_page_content(page["path"])
print(json.dumps(page_dict, indent=2))

# Step 2: Reason
print("\n[2] Analyzing staleness (qwen-plus)...")
reasoning = analyze_staleness(page_dict, client)
print(json.dumps(reasoning, indent=2))

# Step 3: Generate
print("\n[3] Generating refresh (qwen-max)...")
refreshed = generate_refresh(page_dict, reasoning, client)
print(json.dumps(refreshed, indent=2))

print(f"\n{'='*60}")
print("Day 4 complete ✅")