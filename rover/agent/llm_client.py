from __future__ import annotations

import os
import time
import sys

from anthropic import Anthropic, APITimeoutError, RateLimitError, APIStatusError

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0
MIN_REPORT_LENGTH = 500


def generate_report(system_prompt: str, user_prompt: str) -> str:
    client = Anthropic(api_key=os.environ["LLM_API_KEY"])

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=120.0,
            )
            text = response.content[0].text

            if len(text) < MIN_REPORT_LENGTH:
                raise ValueError(
                    f"LLM response too short ({len(text)} chars, minimum {MIN_REPORT_LENGTH}). "
                    f"Likely a truncated or degenerate response."
                )

            return text

        except (APITimeoutError, RateLimitError) as exc:
            last_error = exc
            wait = RETRY_BACKOFF_BASE ** attempt
            print(
                f"  LLM attempt {attempt + 1}/{MAX_RETRIES} failed ({type(exc).__name__}), "
                f"retrying in {wait:.0f}s...",
                file=sys.stderr,
            )
            time.sleep(wait)

        except APIStatusError as exc:
            if exc.status_code >= 500:
                last_error = exc
                wait = RETRY_BACKOFF_BASE ** attempt
                print(
                    f"  LLM server error (HTTP {exc.status_code}), "
                    f"retrying in {wait:.0f}s...",
                    file=sys.stderr,
                )
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(
        f"LLM report generation failed after {MAX_RETRIES} attempts: {last_error}"
    )
