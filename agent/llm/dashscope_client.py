# agent/llm/dashscope_client.py
# ⚠️  ALIBABA CLOUD PROOF ARTIFACT — Alibaba Cloud Model Studio (MaaS)
#
# Uses OpenAI-compatible endpoint to call:
#   - qwen-plus  → reasoning (staleness analysis)
#   - qwen-max   → generation (content refresh)

import os
import json
import logging
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DashScopeClient:

    def __init__(self):
        api_key = os.getenv("ALIBABA_API_KEY")
        base_url = os.getenv("ALIBABA_BASE_URL")
        if not api_key:
            raise EnvironmentError("ALIBABA_API_KEY not set")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _call(self, model: str, messages: list) -> str:
        """Internal: call a model and track token usage."""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        usage = response.usage
        self.total_input_tokens += usage.prompt_tokens
        self.total_output_tokens += usage.completion_tokens
        self.log_budget_status()
        return response.choices[0].message.content

    def reason(self, prompt: str) -> str:
        """Call qwen-plus for staleness reasoning."""
        return self._call(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}]
        )

    def generate(self, prompt: str) -> str:
        """Call qwen-max for content generation."""
        return self._call(
            model="qwen-max",
            messages=[{"role": "user", "content": prompt}]
        )

    def log_budget_status(self):
        """Print running token totals as a rough budget check."""
        logger.info(f"[BUDGET] Input tokens: {self.total_input_tokens} | Output tokens: {self.total_output_tokens}")