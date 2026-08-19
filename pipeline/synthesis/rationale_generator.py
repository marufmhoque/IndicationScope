"""LLM rationale synthesis for top-N white-space candidates.

Uses SYNTHESIS_MODEL (claude-sonnet). Only fires for the top N cells
(configured via SYNTHESIS_TOP_N) to control cost. Retrieval-augmented only —
the prompt supplies all source material; the model must not draw on training memory.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import anthropic

from config import SYNTHESIS_MODEL

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesis_prompt.txt"
_MAX_TOKENS = 800


def generate_rationale(cell: dict, abstracts: list[str], trial_summaries: list[str]) -> dict:
    """
    Generate a rationale narrative for a MatrixCell.

    Args:
        cell: MatrixCell dict (mechanism_class, indication, supporting IDs, etc.)
        abstracts: Relevant PubMed abstract texts (supplied context only).
        trial_summaries: Relevant CT.gov trial title/summary texts.

    Returns:
        dict with keys: rationale (str | None), supporting_pmids (list), supporting_nct_ids (list)
    """
    fallback = {
        "rationale": None,
        "supporting_pmids": cell.get("supporting_pmids", []),
        "supporting_nct_ids": cell.get("supporting_nct_ids", []),
    }

    if not abstracts and not trial_summaries:
        return fallback

    client = _client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY not set — skipping rationale synthesis")
        return fallback

    context = _build_context(abstracts, trial_summaries)
    # Plain substring replace, not str.format — safer against any incidental
    # braces in prompt text and consistent with entity_extraction's approach.
    prompt = (
        _load_prompt()
        .replace("{mechanism_class}", cell.get("mechanism_class") or "Unclassified")
        .replace("{indication}", cell.get("indication") or "")
        .replace("{context}", context)
    )

    try:
        response = client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        parsed = _parse_json_object(response.content[0].text)
    except Exception:
        logger.exception(
            "Rationale synthesis failed for mechanism_class=%r", cell.get("mechanism_class")
        )
        return fallback

    if not parsed:
        return fallback

    return {
        "rationale": parsed.get("rationale"),
        "supporting_pmids": parsed.get("supporting_pmids") or fallback["supporting_pmids"],
        "supporting_nct_ids": parsed.get("supporting_nct_ids") or fallback["supporting_nct_ids"],
    }


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _build_context(abstracts: list[str], trial_summaries: list[str]) -> str:
    parts = [f"[Publication {i}]\n{text}" for i, text in enumerate(abstracts, 1)]
    parts += [f"[Trial {i}]\n{text}" for i, text in enumerate(trial_summaries, 1)]
    return "\n\n".join(parts)


def _parse_json_object(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        logger.warning("Could not parse synthesis response as JSON: %r", raw[:200])
        return None


def _load_prompt() -> str:
    """Read the prompt file, stripping the leading '# ...' header comments
    that document the file for repo readers — those aren't meant for the model."""
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    body_start = next(
        (i for i, line in enumerate(lines) if line.strip() and not line.lstrip().startswith("#")),
        0,
    )
    return "\n".join(lines[body_start:])


def _client() -> anthropic.Anthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)
