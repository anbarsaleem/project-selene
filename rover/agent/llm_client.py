from __future__ import annotations

import os

from anthropic import Anthropic


def generate_report(system_prompt: str, user_prompt: str) -> str:
    client = Anthropic(api_key=os.environ["LLM_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text
