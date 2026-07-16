# agent/writer.py
import os
import requests
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AEM_HOST = os.getenv("AEM_HOST", "http://localhost:4502")
AEM_USER = os.getenv("AEM_USER", "admin")
AEM_PASSWORD = os.getenv("AEM_PASSWORD", "admin")

# Properties we never touch — structural JCR fields
SKIP_PROPERTIES = {
    "jcr:primaryType", "sling:resourceType", "jcr:created",
    "jcr:createdBy", "jcr:lastModified", "jcr:lastModifiedBy",
    "cq:template", "cq:lastModified", "cq:lastModifiedBy",
    "layout", "textIsRich", "jcr:mixinTypes", "singleExpansion"
}

# Properties that contain actual content we refresh
CONTENT_PROPERTIES = {"jcr:title", "jcr:description", "text", "cq:panelTitle"}


def write_refreshed_content(page_path: str, refreshed: dict, original: dict, dry_run: bool = False):
    """
    Diff original and modified JCR trees.
    POST only changed content properties to their exact JCR node paths.
    """
    if dry_run:
        logger.info(f"[WRITER] DRY RUN — would write to {page_path}")
        return {"status": "dry_run", "path": page_path}

    original_tree = original.get("jcr_tree", {})
    modified_tree = refreshed.get("jcr_tree", {})

    changes = []
    collect_changes(original_tree, modified_tree, f"{page_path}", changes)

    if not changes:
        logger.info(f"[WRITER] No changes detected for {page_path}")
        return {"status": "no_changes", "path": page_path}

    # Group changes by node path and POST each node once
    nodes = {}
    for change in changes:
        node_path = change["node_path"]
        if node_path not in nodes:
            nodes[node_path] = {}
        nodes[node_path][change["property"]] = change["new_value"]

    results = []
    for node_path, properties in nodes.items():
        url = f"{AEM_HOST}{node_path}"
        result = sling_post(url, properties)
        results.append(result)
        logger.info(f"[WRITER] Updated {node_path} — {list(properties.keys())}")

    return {"status": "written", "path": page_path, "updates": results}


def collect_changes(original: dict, modified: dict, current_path: str, changes: list):
    """
    Recursively diff two JCR trees.
    Collect only content property changes — skip structural properties.
    """
    for key, new_value in modified.items():
        if key in SKIP_PROPERTIES:
            continue

        original_value = original.get(key)

        if isinstance(new_value, dict):
            # Recurse into child nodes
            original_child = original.get(key, {})
            collect_changes(original_child, new_value, f"{current_path}/{key}", changes)

        elif isinstance(new_value, str):
            if key in CONTENT_PROPERTIES and new_value != original_value:
                changes.append({
                    "node_path": current_path,
                    "property": key,
                    "original_value": original_value,
                    "new_value": new_value
                })


def rollback_content(page_path: str, original: dict):
    """
    Restore original JCR tree — POST original values back to each node.
    """
    original_tree = original.get("jcr_tree", {})
    changes = []
    collect_changes({}, original_tree, page_path, changes)

    nodes = {}
    for change in changes:
        node_path = change["node_path"]
        if node_path not in nodes:
            nodes[node_path] = {}
        nodes[node_path][change["property"]] = change["new_value"]

    results = []
    for node_path, properties in nodes.items():
        url = f"{AEM_HOST}{node_path}"
        result = sling_post(url, properties)
        results.append(result)
        logger.info(f"[WRITER] Rolled back {node_path}")

    return {"status": "rolled_back", "path": page_path, "updates": results}


def sling_post(url: str, data: dict) -> dict:
    """Make a single Sling POST."""
    try:
        response = requests.post(
            url,
            data=data,
            auth=(AEM_USER, AEM_PASSWORD),
            timeout=10
        )
        if not response.ok:
            logger.error(f"[WRITER] AEM {response.status_code} at {url}: {response.text[:200]}")
            response.raise_for_status()
        return {"url": url, "status": response.status_code}
    except requests.exceptions.RequestException as e:
        logger.error(f"[WRITER] Failed POST to {url}: {e}")
        raise