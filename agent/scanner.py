# agent/scanner.py
# JCR Stale Page Scanner — uses AEM QueryBuilder API

import os
import requests
import logging
from datetime import datetime, timezone, timedelta
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AEM_HOST = os.getenv("AEM_HOST", "http://localhost:4502")
AEM_USER = os.getenv("AEM_USER", "admin")
AEM_PASSWORD = os.getenv("AEM_PASSWORD", "admin")
STALE_THRESHOLD_DAYS = int(os.getenv("STALE_THRESHOLD_DAYS", "90"))
AEM_CONTENT_PATH = os.getenv("AEM_CONTENT_PATH", "/content/myaemproject")


def get_threshold_timestamp() -> str:
    cutoff = datetime.now() - timedelta(days=STALE_THRESHOLD_DAYS)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

def scan_stale_pages() -> list[dict]:
    """
    Query AEM via QueryBuilder for pages not modified in STALE_THRESHOLD_DAYS.
    Handles pagination automatically.
    Returns list of { path, title, last_modified, template }
    """
    all_pages = []
    offset = 0
    page_size = 10
    threshold = get_threshold_timestamp()

    logger.info(f"[SCANNER] Looking for pages not modified since {threshold}")

    while True:
        params = {
            "path": AEM_CONTENT_PATH,
            "type": "cq:Page",
            "daterange.property": "jcr:content/cq:lastModified",
            "daterange.upperBound": threshold,
            "daterange.upperOperation": "<=",
            "p.limit": page_size,
            "p.offset": offset,
            "p.hits": "full",
            "p.nodedepth": "2"
        }
        query_string = urllib.parse.urlencode(params)
        logger.info(f"[SCANNER] QueryBuilder URL: {AEM_HOST}/bin/querybuilder.json?{query_string}")

        try:
            response = requests.get(
                f"{AEM_HOST}/bin/querybuilder.json",
                params=params,
                auth=(AEM_USER, AEM_PASSWORD),
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"[SCANNER] Failed to query AEM: {e}")
            break

        data = response.json()
        hits = data.get("hits", [])

        if not hits:
            break

        for hit in hits:
            jcr_content = hit.get("jcr:content", {})
            all_pages.append({
                "path": hit.get("jcr:path", ""),
                "title": jcr_content.get("jcr:title", "Untitled"),
                "last_modified": jcr_content.get("cq:lastModified", ""),
                "template": jcr_content.get("cq:template", "")
            })

        logger.info(f"[SCANNER] Fetched {len(hits)} pages at offset {offset}")

        if len(hits) < page_size:
            break

        offset += page_size

    logger.info(f"[SCANNER] Found {len(all_pages)} stale pages total")
    return all_pages