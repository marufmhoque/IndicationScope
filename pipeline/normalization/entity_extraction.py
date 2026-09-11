"""LLM-based mechanism/target extraction from intervention names and abstracts.

Uses EXTRACTION_MODEL (claude-haiku) for high-volume cheap extraction.
Every extraction retains a pointer to its source NCT ID or PMID.

A single search can involve hundreds of trials/publications; callers should
pre-cap how many items they pass in so a scan stays within an interactive
time budget (matrix_builder does this). _MAX_ITEMS is a hard safety ceiling
here regardless. Calls run in parallel since each is small and independent.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

from config import EXTRACTION_MODEL
from pipeline.ingestion.cache import MechanismCache

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parents[1] / "synthesis" / "prompts" / "extraction_prompt.txt"
_MAX_ITEMS = 80
_MAX_WORKERS = 16
_MAX_TOKENS = 200
_TEXT_LIMIT = 1000

# Constructed on first use, not at import — module-scope construction of a
# filesystem-backed object is what once turned a read-only disk into a
# boot-time 500 on every route.
_cache: MechanismCache | None = None


def _mechanism_cache() -> MechanismCache:
    global _cache
    if _cache is None:
        _cache = MechanismCache()
    return _cache


def extract_mechanisms_batch(items: list[dict]) -> dict[str, dict]:
    """
    Classify mechanism class for a list of {source_id, text} items.

    source_id must be a stable identity for the thing being classified (a
    normalised drug name, or a PMID) rather than a per-query id, because results
    are cached under it and reused by later searches.

    Returns a dict keyed by source_id -> {mechanism_class, target, drug_class}.
    Items with blank text, and any beyond _MAX_ITEMS, are skipped.
    """
    usable = [it for it in items if it.get("text", "").strip()][:_MAX_ITEMS]
    if not usable:
        return {}

    cache = _mechanism_cache()
    results: dict[str, dict] = dict(cache.get_many([it["source_id"] for it in usable]))
    pending = [it for it in usable if it["source_id"] not in results]
    if not pending:
        logger.info("All %d items served from the mechanism cache", len(usable))
        return results

    client = _client()
    if client is None:
        logger.warning(
            "ANTHROPIC_API_KEY not set — skipping mechanism extraction for %d items",
            len(pending),
        )
        return results

    prompt_template = _load_prompt()
    fresh: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {
            executor.submit(_extract_one, client, prompt_template, it["text"]): it["source_id"]
            for it in pending
        }
        api_error_count = 0
        for future in as_completed(futures):
            source_id = futures[future]
            try:
                fresh[source_id] = future.result()
            except anthropic.APIError as exc:
                # Expected/recoverable (rate limit, billing, timeout) — one
                # line per batch instead of a full traceback per item.
                api_error_count += 1
                logger.debug("Extraction API error for source_id=%s: %s", source_id, exc)
            except Exception:
                logger.exception("Mechanism extraction failed for source_id=%s", source_id)

        if api_error_count:
            logger.warning(
                "%d/%d extraction calls failed with an API error (rate limit, billing, or "
                "timeout) — those items fall back to Unclassified",
                api_error_count, len(pending),
            )

    # Only cache real classifications; a null result may just mean the call failed,
    # and caching that would make a transient outage permanent.
    cache.set_many({k: v for k, v in fresh.items() if v.get("mechanism_class")})
    results.update(fresh)
    return results


def extract_mechanism(text: str, source_id: str) -> dict:
    """Single-item convenience wrapper around extract_mechanisms_batch."""
    batch = extract_mechanisms_batch([{"source_id": source_id, "text": text}])
    result = batch.get(source_id, {"mechanism_class": None, "target": None, "drug_class": None})
    return {**result, "source_id": source_id}


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------

def _extract_one(client: anthropic.Anthropic, prompt_template: str, text: str) -> dict:
    # A plain substring replace, not str.format — the prompt's JSON example
    # contains literal { } that format() would try (and fail) to interpret.
    prompt = prompt_template.replace("{text}", text[:_TEXT_LIMIT])
    response = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_object(_response_text(response))


def _response_text(response) -> str:
    """Return the first text block's content.

    Not content[0]: models with thinking enabled put a ThinkingBlock first, so
    indexing blindly raises AttributeError. Block order is a model property, not
    something this code should depend on.
    """
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {
                "mechanism_class": parsed.get("mechanism_class"),
                "target": parsed.get("target"),
                "drug_class": parsed.get("drug_class"),
            }
    except json.JSONDecodeError:
        pass
    logger.warning("Could not parse extraction response as JSON: %r", raw[:200])
    return {"mechanism_class": None, "target": None, "drug_class": None}


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
