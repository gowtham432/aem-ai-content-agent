# agent/extractor.py
import os
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AEM_HOST = os.getenv("AEM_HOST", "http://localhost:4502")
AEM_USER = os.getenv("AEM_USER", "admin")
AEM_PASSWORD = os.getenv("AEM_PASSWORD", "admin")


def extract_page_content(page_path: str) -> dict:
    """
    Fetch raw .infinity.json from AEM.
    Returns the full JCR tree as-is — no parsing, no walking.
    Model will handle structure.
    """
    url = f"{AEM_HOST}{page_path}.infinity.json"

    try:
        response = requests.get(
            url,
            auth=(AEM_USER, AEM_PASSWORD),
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[EXTRACTOR] Failed to fetch {page_path}: {e}")
        return {}

    data = response.json()

    logger.info(f"[EXTRACTOR] Fetched raw JCR tree for {page_path}")

    return {
        "path": page_path,
        "jcr_tree": data
    }