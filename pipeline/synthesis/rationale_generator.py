"""LLM synthesis over ingested evidence.

Uses SYNTHESIS_MODEL. Retrieval-augmented only — the prompt supplies all source
material and the model must not draw on training memory. Every entry point is
deliberately cheap to fail: synthesis is enrichment, so any error degrades to
None and the caller renders without it.

All three prompts are written to report rather than evaluate: they describe what
the sources state and never characterise a mechanism or disease area as an
opportunity, crowded, promising or otherwise.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import anthropic

from config import SYNTHESIS_MODEL

logger = logging.getLogger(__name__)

_PROMPTS = Path(__file__).parent / "prompts"
_SYNTHESIS_PROMPT = _PROMPTS / "synthesis_prompt.txt"
_FAILURE_PROMPT = _PROMPTS / "failure_prompt.txt"
_BRIEFING_PROMPT = _PROMPTS / "executive_briefing_prompt.txt"

# Thinking tokens count against max_tokens. At 800 the model spent the whole
# allowance reasoning and returned no text at all (stop_reason: max_tokens), so
# this needs real headroom above the JSON it has to emit.
_MAX_TOKENS = 4000

# The brief writes six sections of continuous prose, well beyond a single
# evidence summary, so it gets proportionally more room.
_BRIEFING_MAX_TOKENS = 8000

# Structured summarisation over supplied sources rather than hard reasoning. Low
# effort keeps latency and output-token spend down without costing accuracy here.
_EFFORT = "low"

_FAILURE_CATEGORIES = frozenset(
    ["safety", "efficacy", "enrolment", "business", "unknown"]
)

BRIEFING_SECTIONS = (
    "disease_overview",
    "molecular_mechanisms",
    "epidemiology",
    "standard_of_treatment",
    "current_research",
    "historical_failures",
)


def generate_rationale(cell: dict, abstracts: list[str], trial_summaries: list[str]) -> dict:
    """Summarise the evidence for one mechanism in one disease.

    Returns dict with keys: rationale (str | None), supporting_pmids,
    supporting_nct_ids. The key is still "rationale" for API compatibility; the
    content is a factual evidence summary.
    """
    fallback = {
        "rationale": None,
        "supporting_pmids": cell.get("supporting_pmids", []),
        "supporting_nct_ids": cell.get("supporting_nct_ids", []),
    }

    parsed = _synthesize(_SYNTHESIS_PROMPT, cell, abstracts, trial_summaries)
    if not parsed:
        return fallback

    return {
        "rationale": parsed.get("rationale"),
        "supporting_pmids": parsed.get("supporting_pmids") or fallback["supporting_pmids"],
        "supporting_nct_ids": parsed.get("supporting_nct_ids") or fallback["supporting_nct_ids"],
    }


def generate_failure_analysis(
    cell: dict, abstracts: list[str], trial_summaries: list[str]
) -> dict:
    """Summarise why prior trials of this mechanism in this disease stopped.

    Returns dict with keys: summary (str | None), failure_points (list of
    {reason, category, citations}).

    An empty failure_points list is a legitimate result, not an error: stated
    stop reasons are often absent or administrative ("Business Reasons"), and the
    prompt requires saying so rather than inventing a scientific explanation.
    """
    fallback = {"summary": None, "failure_points": []}

    parsed = _synthesize(_FAILURE_PROMPT, cell, abstracts, trial_summaries)
    if not parsed:
        return fallback

    return {
        "summary": parsed.get("summary"),
        "failure_points": _clean_failure_points(parsed.get("failure_points")),
    }


def generate_executive_briefing(
    indication: str,
    context: str,
    coverage_note: str,
    background: str,
) -> dict:
    """Write the six-section disease intelligence brief.

    Args:
        indication: the disease searched.
        context: aggregated scan evidence — mechanisms with targets and counts,
            phase mix, publication trend, organisations, stopped trials with
            their registered reasons, and sampled records.
        coverage_note: how much of each corpus the scan examined, so statements
            are calibrated to a sample rather than written as a census.
        background: relevance-ranked abstracts retrieved for disease overview,
            epidemiology and cost of illness, which the scan's recency-ordered
            sample does not supply.

    Returns a dict of the six sections, each str | None. Sections are
    independent so a partial response degrades to gaps rather than nothing.
    """
    empty = {section: None for section in BRIEFING_SECTIONS}

    if not context.strip() and not background.strip():
        return empty

    client = _client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY not set — skipping disease brief")
        return empty

    prompt = (
        _load_prompt(_BRIEFING_PROMPT)
        .replace("{coverage_note}", coverage_note)
        .replace("{indication}", indication)
        .replace("{context}", context or "(none)")
        .replace("{background}", background or "(none)")
    )

    try:
        response = client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=_BRIEFING_MAX_TOKENS,
            output_config={"effort": _EFFORT},
            messages=[{"role": "user", "content": prompt}],
        )
        parsed = _parse_json_object(_response_text(response))
    except Exception:
        logger.exception("Disease brief failed for indication=%r", indication)
        return empty

    if not parsed:
        return empty

    return {section: (parsed.get(section) or None) for section in BRIEFING_SECTIONS}


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _synthesize(
    prompt_path: Path,
    cell: dict,
    abstracts: list[str],
    trial_summaries: list[str],
) -> dict | None:
    """Shared call path: no sources or no key means no call at all."""
    if not abstracts and not trial_summaries:
        return None

    client = _client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY not set — skipping synthesis")
        return None

    # Plain substring replace, not str.format — the prompts contain literal JSON
    # braces that format() would try (and fail) to interpret as fields.
    prompt = (
        _load_prompt(prompt_path)
        .replace("{mechanism_class}", cell.get("mechanism_class") or "Unclassified")
        .replace("{indication}", cell.get("indication") or "")
        .replace("{context}", _build_context(abstracts, trial_summaries))
    )

    try:
        response = client.messages.create(
            model=SYNTHESIS_MODEL,
            max_tokens=_MAX_TOKENS,
            output_config={"effort": _EFFORT},
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json_object(_response_text(response))
    except Exception:
        logger.exception(
            "Synthesis failed (%s) for mechanism_class=%r",
            prompt_path.name, cell.get("mechanism_class"),
        )
        return None


def _clean_failure_points(raw) -> list[dict]:
    """Keep only well-formed points, and pin category to the known set.

    An unrecognised category would break the UI's badge mapping, and dropping the
    whole point would lose a real finding — so the reason survives and only the
    category falls back.
    """
    if not isinstance(raw, list):
        return []

    points = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        reason = (item.get("reason") or "").strip()
        if not reason:
            continue
        category = (item.get("category") or "").strip().lower()
        citations = item.get("citations")
        points.append(
            {
                "reason": reason,
                "category": category if category in _FAILURE_CATEGORIES else "unknown",
                "citations": [str(c) for c in citations] if isinstance(citations, list) else [],
            }
        )
    return points


def _build_context(abstracts: list[str], trial_summaries: list[str]) -> str:
    """Sources carry their own PMID/NCT identifier, so they are labelled by kind
    only — numbering them invites the model to cite the position ("Publication 1")
    instead of the identifier the prompt asks for."""
    parts = [f"[Publication]\n{text}" for text in abstracts]
    parts += [f"[Trial]\n{text}" for text in trial_summaries]
    return "\n\n".join(parts)


def _response_text(response) -> str:
    """Return the first text block's content.

    Not content[0]: models with thinking enabled put a ThinkingBlock first, so
    indexing blindly raises AttributeError.
    """
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _parse_json_object(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    if not text:
        # Almost always the model exhausting max_tokens on thinking before
        # emitting anything — silent otherwise.
        logger.warning("Synthesis returned no text block (check max_tokens vs thinking)")
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        logger.warning("Could not parse synthesis response as JSON: %r", raw[:200])
        return None


def _load_prompt(path: Path) -> str:
    """Read a prompt file, stripping the leading '# ...' header comments that
    document the file for repo readers — those aren't meant for the model."""
    text = path.read_text(encoding="utf-8")
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
