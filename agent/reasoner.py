# agent/reasoner.py
import json
import logging
from agent.llm.dashscope_client import DashScopeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_staleness(page_dict: dict, client: DashScopeClient) -> dict:
    """
    Send raw JCR tree to qwen-plus for staleness analysis.
    Returns: { staleness_reason, fields_to_update, refresh_direction }
    """

    prompt = f"""You are an AEM content auditor. You will receive a raw AEM JCR JSON tree for a page.

Analyze the content and identify:
1. Why is this content stale?
2. Which specific fields need updating? Reference them by their JCR path (e.g. jcr:content/jcr:title, jcr:content/root/container/container/text/text)
3. What tone and direction should the refresh take?

Raw JCR tree:
{json.dumps(page_dict.get("jcr_tree", {}), indent=2)}

Respond ONLY with valid JSON in this exact format, no extra text:
{{
  "staleness_reason": "explain why this content is stale",
  "fields_to_update": ["jcr:content/jcr:title", "jcr:content/root/..."],
  "refresh_direction": "explain tone and direction for the refresh"
}}"""

    logger.info(f"[REASONER] Analyzing staleness for {page_dict.get('path')}")

    raw = client.reason(prompt)

    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(clean)
        logger.info(f"[REASONER] Analysis complete — fields: {result.get('fields_to_update')}")
        return result
    except json.JSONDecodeError:
        logger.error(f"[REASONER] Failed to parse JSON: {raw}")
        return {
            "staleness_reason": raw,
            "fields_to_update": [],
            "refresh_direction": ""
        }