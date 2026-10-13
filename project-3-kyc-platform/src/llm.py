"""Chat model construction and reply text extraction shared by the agent nodes.

``DEFAULT_MODEL`` picks the provider: a name containing "claude" routes to
ChatAnthropic, anything else to ChatOpenAI.

Claude Haiku 5.5 (the default since 2026-10-13) rejects a non-default
``temperature``, so none is sent to Anthropic. It thinks by default, and the
thinking counts toward ``max_tokens``; ``effort="low"`` keeps the thinking
short, and ``max_tokens`` is set explicitly because langchain-anthropic 1.4.0
does not know this model and would otherwise fall back to 4096. Models older
than the 4.6 family reject the effort setting; set ``CLAUDE_EFFORT`` to an
empty string to send none. With thinking on, a reply's ``content`` is a list of
blocks (thinking, then text) rather than a string, so callers read replies
through ``message_text``.
"""

from __future__ import annotations

import os

ANTHROPIC_MAX_TOKENS = 8192
DEFAULT_ANTHROPIC_EFFORT = "low"
ANTHROPIC_EFFORT_ENV_VAR = "CLAUDE_EFFORT"


def build_chat_model(model_name: str):
    """Return the LangChain chat model for ``model_name``."""
    if "claude" in model_name:
        from langchain_anthropic import ChatAnthropic

        effort = os.getenv(ANTHROPIC_EFFORT_ENV_VAR, DEFAULT_ANTHROPIC_EFFORT).strip() or None
        return ChatAnthropic(model=model_name, max_tokens=ANTHROPIC_MAX_TOKENS, effort=effort)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model_name, temperature=0)


def message_text(message) -> str:
    """Return the text of an LLM reply, ignoring thinking and other non-text blocks."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "".join(parts)
