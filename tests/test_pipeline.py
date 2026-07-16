# tests/test_pipeline.py
# Run with: pytest tests/test_pipeline.py -v

import pytest
import json
import os
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

load_dotenv()


# ── Scanner tests ─────────────────────────────────────────

def test_scanner_returns_list():
    """Scanner should return a list even if empty."""
    from agent.scanner import scan_stale_pages
    result = scan_stale_pages()
    assert isinstance(result, list)


def test_scanner_item_has_required_keys():
    """Each scanner result must have path, title, last_modified, template."""
    from agent.scanner import scan_stale_pages
    results = scan_stale_pages()
    if results:
        for page in results:
            assert "path" in page
            assert "title" in page
            assert "last_modified" in page
            assert "template" in page


# ── Extractor tests ───────────────────────────────────────

def test_extractor_returns_dict():
    """Extractor should return a dict with path and jcr_tree."""
    from agent.extractor import extract_page_content
    result = extract_page_content("/content/myaemproject/us/en/cloud-migration-services-2021")
    assert isinstance(result, dict)
    assert "path" in result
    assert "jcr_tree" in result


def test_extractor_handles_missing_page():
    """Extractor should return empty dict on missing page, not crash."""
    from agent.extractor import extract_page_content
    result = extract_page_content("/content/myaemproject/us/en/page-that-does-not-exist")
    assert isinstance(result, dict)


def test_extractor_jcr_tree_has_content():
    """jcr_tree should contain jcr:content node."""
    from agent.extractor import extract_page_content
    result = extract_page_content("/content/myaemproject/us/en/cloud-migration-services-2021")
    if result:
        jcr_tree = result.get("jcr_tree", {})
        assert "jcr:content" in jcr_tree


# ── Reasoner tests ────────────────────────────────────────

def test_reasoner_returns_required_keys():
    """Reasoner output must have staleness_reason, fields_to_update, refresh_direction."""
    from agent.reasoner import analyze_staleness

    mock_client = MagicMock()
    mock_client.reason.return_value = json.dumps({
        "staleness_reason": "Content is outdated",
        "fields_to_update": ["jcr:content/jcr:title"],
        "refresh_direction": "Use modern tone"
    })

    page_dict = {
        "path": "/content/test",
        "jcr_tree": {
            "jcr:content": {
                "jcr:title": "Old Title",
                "jcr:description": "Old description"
            }
        }
    }

    result = analyze_staleness(page_dict, mock_client)
    assert "staleness_reason" in result
    assert "fields_to_update" in result
    assert "refresh_direction" in result


def test_reasoner_handles_bad_json():
    """Reasoner should not crash if model returns non-JSON."""
    from agent.reasoner import analyze_staleness

    mock_client = MagicMock()
    mock_client.reason.return_value = "Sorry I cannot help with that"

    page_dict = {"path": "/content/test", "jcr_tree": {}}
    result = analyze_staleness(page_dict, mock_client)

    assert isinstance(result, dict)
    assert "staleness_reason" in result


# ── Generator tests ───────────────────────────────────────

def test_generator_returns_jcr_tree():
    """Generator output must have path and jcr_tree."""
    from agent.generator import generate_refresh

    mock_client = MagicMock()
    mock_client.generate.return_value = json.dumps({
        "jcr:content": {
            "jcr:title": "Refreshed Title",
            "jcr:description": "Refreshed description"
        }
    })

    page_dict = {
        "path": "/content/test",
        "jcr_tree": {
            "jcr:content": {
                "jcr:title": "Old Title"
            }
        }
    }

    reasoning = {
        "staleness_reason": "Outdated",
        "fields_to_update": ["jcr:content/jcr:title"],
        "refresh_direction": "Modernize"
    }

    result = generate_refresh(page_dict, reasoning, mock_client)
    assert "path" in result
    assert "jcr_tree" in result


def test_generator_handles_bad_json():
    """Generator should return original tree if model returns non-JSON."""
    from agent.generator import generate_refresh

    mock_client = MagicMock()
    mock_client.generate.return_value = "not valid json at all"

    page_dict = {
        "path": "/content/test",
        "jcr_tree": {"jcr:content": {"jcr:title": "Old"}}
    }

    result = generate_refresh(page_dict, {}, mock_client)
    assert isinstance(result, dict)
    assert "jcr_tree" in result


# ── Writer tests ──────────────────────────────────────────

def test_writer_dry_run_does_not_call_aem():
    """Writer in dry_run mode should not make any HTTP calls."""
    from agent.writer import write_refreshed_content

    with patch("agent.writer.requests.post") as mock_post:
        result = write_refreshed_content(
            "/content/test",
            {"path": "/content/test", "jcr_tree": {}},
            {"path": "/content/test", "jcr_tree": {}},
            dry_run=True
        )
        mock_post.assert_not_called()
        assert result["status"] == "dry_run"


def test_writer_detects_no_changes():
    """Writer should return no_changes if original and refreshed are identical."""
    from agent.writer import write_refreshed_content

    tree = {
        "jcr:content": {
            "jcr:title": "Same Title",
            "jcr:description": "Same Description"
        }
    }

    result = write_refreshed_content(
        "/content/test",
        {"path": "/content/test", "jcr_tree": tree},
        {"path": "/content/test", "jcr_tree": tree},
        dry_run=False
    )
    assert result["status"] == "no_changes"


def test_writer_collects_correct_changes():
    """Writer should detect changed content properties and skip structural ones."""
    from agent.writer import collect_changes

    original = {
        "jcr:content": {
            "jcr:primaryType": "cq:PageContent",
            "jcr:title": "Old Title",
            "jcr:description": "Old Description",
            "sling:resourceType": "myaemproject/components/page"
        }
    }

    modified = {
        "jcr:content": {
            "jcr:primaryType": "cq:PageContent",
            "jcr:title": "New Title",
            "jcr:description": "New Description",
            "sling:resourceType": "myaemproject/components/page"
        }
    }

    changes = []
    collect_changes(original, modified, "/content/test", changes)

    assert len(changes) == 2
    paths = [c["property"] for c in changes]
    assert "jcr:title" in paths
    assert "jcr:description" in paths


# ── DB tests ──────────────────────────────────────────────

def test_db_insert_and_fetch():
    """Insert an entry and fetch it back by ID."""
    import os
    os.environ["DB_PATH"] = "test_audit.db"

    from db.audit import init_db, insert_entry, get_entry_by_id
    import db.audit as audit_module
    audit_module.DB_PATH = "test_audit.db"

    init_db()

    page_dict = {"path": "/content/test", "jcr_tree": {"jcr:content": {"jcr:title": "Test"}}}
    refreshed = {"path": "/content/test", "jcr_tree": {"jcr:content": {"jcr:title": "Refreshed"}}}
    reasoning = {"staleness_reason": "Old", "fields_to_update": [], "refresh_direction": "Modernize"}

    entry_id = insert_entry(page_dict, refreshed, reasoning)
    assert entry_id is not None

    fetched = get_entry_by_id(entry_id)
    assert fetched is not None
    assert fetched["page_path"] == "/content/test"

    # Cleanup
    os.remove("test_audit.db")


def test_db_update_action():
    """Mark an entry as approved and verify the status updates."""
    from db.audit import init_db, insert_entry, update_action, get_entry_by_id
    import db.audit as audit_module
    audit_module.DB_PATH = "test_audit2.db"

    init_db()

    page_dict = {"path": "/content/test2", "jcr_tree": {}}
    entry_id = insert_entry(page_dict, {}, {})

    update_action(entry_id, "approved")
    fetched = get_entry_by_id(entry_id)
    assert fetched["reviewer_action"] == "approved"

    os.remove("test_audit2.db")