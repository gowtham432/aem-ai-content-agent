# api/main.py
# FastAPI backend — run with: uvicorn api.main:app --reload

import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.scanner import scan_stale_pages
from agent.extractor import extract_page_content
from agent.reasoner import analyze_staleness
from agent.generator import generate_refresh
from agent.writer import write_refreshed_content
from agent.llm.dashscope_client import DashScopeClient
from db.audit import init_db, insert_entry, get_queue, get_all_entries, update_action, get_entry_by_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stale Content Refresh Agent", version="0.1.0")

# Init DB on startup
init_db()

# Single shared LLM client
llm_client = DashScopeClient()


class RejectRequest(BaseModel):
    reason: str


class ApproveRequest(BaseModel):
    edited_content: dict | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models": {
            "reasoning": "qwen-plus",
            "generation": "qwen-max"
        },
        "tokens_used": {
            "input": llm_client.total_input_tokens,
            "output": llm_client.total_output_tokens
        }
    }


@app.post("/scan")
def scan():
    """
    Run full pipeline: scan → extract → reason → generate.
    Stores results in SQLite queue. Processes up to MAX_PAGES_PER_SCAN pages.
    Skips pages that fail — never lets one bad page crash the batch.
    """
    import os
    max_pages = int(os.getenv("MAX_PAGES_PER_SCAN", "10"))

    logger.info("[API] /scan triggered")
    pages = scan_stale_pages()

    if not pages:
        return {"message": "No stale pages found", "processed": 0}

    pages = pages[:max_pages]
    processed = []
    skipped = []

    for page in pages:
        try:
            # Extract
            page_dict = extract_page_content(page["path"])
            if not page_dict:
                raise ValueError("Extractor returned empty dict")

            # Reason
            reasoning = analyze_staleness(page_dict, llm_client)

            # Generate
            refreshed = generate_refresh(page_dict, reasoning, llm_client)

            # Store in queue
            entry_id = insert_entry(page_dict, refreshed, reasoning)

            processed.append({
                "id": entry_id,
                "path": page["path"]
            })

        except Exception as e:
            logger.error(f"[API] Skipping {page['path']} due to error: {e}")
            skipped.append({"path": page["path"], "error": str(e)})
            continue

    return {
        "message": f"Scan complete",
        "processed": len(processed),
        "skipped": len(skipped),
        "items": processed
    }

@app.get("/")
def root():
    return {"message": "Stale Content Refresh Agent is running", "docs": "/docs"}

@app.get("/queue")
def queue():
    """Return all pending items awaiting human review."""
    items = get_queue()
    # Parse JSON strings back to dicts for readability
    for item in items:
        item["original_content"] = json.loads(item["original_content"])
        item["refreshed_content"] = json.loads(item["refreshed_content"])
        item["reasoning"] = json.loads(item["reasoning"])
    return {"pending": len(items), "items": items}


@app.post("/approve/{entry_id}")
def approve(entry_id: str, body: ApproveRequest = None):
    entry = get_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    original = json.loads(entry["original_content"])
    content_to_write = json.loads(entry["refreshed_content"])

    if body and body.edited_content:
        content_to_write = body.edited_content

    write_refreshed_content(entry["page_path"], content_to_write, original, dry_run=False)
    update_action(entry_id, "approved", json.dumps(body.edited_content) if body and body.edited_content else "")

    return {"message": f"Approved {entry['page_path']}", "id": entry_id}

@app.post("/reject/{entry_id}")
def reject(entry_id: str, body: RejectRequest = None):
    """Reject an item with a reason."""
    entry = get_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    reason = body.reason if body else "No reason provided"
    update_action(entry_id, "rejected", reason)

    return {"message": f"Rejected {entry['page_path']}", "id": entry_id}

@app.post("/rollback/{entry_id}")
def rollback(entry_id: str):
    """Restore original content from SQLite back to JCR."""
    from agent.writer import rollback_content
    from db.audit import mark_rolled_back

    entry = get_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if entry["reviewer_action"] != "approved":
        raise HTTPException(status_code=400, detail="Can only rollback approved entries")

    original = json.loads(entry["original_content"])

    rollback_content(entry["page_path"], original)
    mark_rolled_back(entry_id)

    return {"message": f"Rolled back {entry['page_path']}", "id": entry_id}

@app.get("/audit")
def audit():
    """Return full audit log."""
    items = get_all_entries()
    for item in items:
        item["original_content"] = json.loads(item["original_content"])
        item["refreshed_content"] = json.loads(item["refreshed_content"])
        item["reasoning"] = json.loads(item["reasoning"])
    return {"total": len(items), "items": items}