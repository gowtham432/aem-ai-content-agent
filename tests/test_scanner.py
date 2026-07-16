import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from agent.scanner import scan_stale_pages

pages = scan_stale_pages()

print(f"\nFound {len(pages)} stale pages:\n")
for p in pages:
    print(f"  path:          {p['path']}")
    print(f"  title:         {p['title']}")
    print(f"  last_modified: {p['last_modified']}")
    print(f"  template:      {p['template']}")
    print()