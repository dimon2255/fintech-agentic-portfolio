"""Chat model construction and reply text extraction shared by the agent nodes.

``DEFAULT_MODEL`` picks the provider: a name containing "claude" routes to
ChatAnthropic, anything else to ChatOpenAI.

Claude Haiku 5.5 (the default since 2026-10-13) rejects a non-default
``temperature``, so none is sent to Anthropic. It thinks by default, and the
thinking counts toward ``max_tokens``; ``effort="low"`` keeps the thinking
short, and ``max_tokens`` is set explicitly because langchain-anthropic 1.4.0
does not know this model and would otherwise fall back to 4096. With thinking
on, a reply's ``content`` is a list of blocks (thinking, then text) rather than
a string, so callers read replies through ``message_text``.
"""

from __future__ import annotations

ANTHROPIC_MAX_TOKENS = 8192
ANTHROPIC_EFFORT = "low"


def build_chat_model(model_name: str):
    """Return the LangChain chat model for ``model_name``."""
    if "claude" in model_name:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name, max_tokens=ANTHROPIC_MAX_TOKENS, effort=ANTHROPIC_EFFORT)
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
