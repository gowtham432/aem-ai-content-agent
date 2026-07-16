# agent/generator.py
import json
import logging
from agent.llm.dashscope_client import DashScopeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_refresh(page_dict: dict, reasoning: dict, client: DashScopeClient) -> dict:
    """
    Give raw JCR tree + reasoning to qwen-max.
    Returns a modified copy of the JCR tree with refreshed content in place.
    """

    prompt = f"""You are an AEM content writer. You will receive a raw AEM JCR JSON tree and a staleness analysis.

Your job is to return a modified version of the SAME JSON tree with stale content refreshed in place.

Rules:
- Only modify text content fields (e.g. jcr:title, jcr:description, text properties)
- Do NOT modify structural properties (jcr:primaryType, sling:resourceType, jcr:created, cq:template, layout etc.)
- Keep the exact same JSON structure and all property names
- For accordion items, refresh the text inside each item relevant to its cq:panelTitle
- Preserve HTML tags in text fields that already have them (e.g. <p> tags)
- Return the complete modified JCR tree, not just the changed parts

Original JCR tree:
{json.dumps(page_dict.get("jcr_tree", {}), indent=2)}

Staleness analysis:
{json.dumps(reasoning, indent=2)}

Respond ONLY with the modified JCR JSON tree, no extra text, no markdown fences."""

    logger.info(f"[GENERATOR] Generating refresh for {page_dict.get('path')}")

    raw = client.generate(prompt)

    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        modified_tree = json.loads(clean)
        logger.info(f"[GENERATOR] Modified JCR tree received")
        return {
            "path": page_dict.get("path"),
            "jcr_tree": modified_tree
        }
    except json.JSONDecodeError:
        logger.error(f"[GENERATOR] Failed to parse response: {raw[:200]}")
        return {
            "path": page_dict.get("path"),
            "jcr_tree": page_dict.get("jcr_tree", {})
        }