"""LLM synthesis over an already-scored matrix cell.

Uses SYNTHESIS_MODEL. Retrieval-augmented only — the prompt supplies all source
material and the model must not draw on training memory. Both entry points are
deliberately cheap to fail: a synthesis is enrichment, so any error degrades to
None and the caller renders the cell without it.

Persona is a *lens*, not a filter. It changes how the same evidence is framed —
what a researcher, a founder, and a diligence analyst each need from it — and
never what was searched or which sources were supplied.
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
_PERSONA_DIR = _PROMPTS / "personas"

# Thinking tokens count against max_tokens. At 800 the model spent the whole
# allowance reasoning and returned a thinking block with no text at all
# (stop_reason: max_tokens), so this needs real headroom above the ~400-token
# JSON it actually has to emit.
_MAX_TOKENS = 4000

# The briefing writes four sections rather than one, so it needs more room
# above the thinking allowance than a single rationale does.
_BRIEFING_MAX_TOKENS = 6000

# These are structured summarisation over supplied sources, not hard
# reasoning. Low effort keeps latency and output-token spend down without
# costing accuracy on this task.
_EFFORT = "low"

DEFAULT_PERSONA = "academic"
PERSONAS = ("academic", "startup", "diligence")

_FAILURE_CATEGORIES = frozenset(
    ["safety", "efficacy", "enrolment", "business", "unknown"]
)


def generate_rationale(
    cell: dict,
    abstracts: list[str],
    trial_summaries: list[str],
    persona: str = DEFAULT_PERSONA,
) -> dict:
    """
    Generate a white-space rationale for a MatrixCell.

    Returns dict with keys: rationale (str | None), supporting_pmids,
    supporting_nct_ids.
    """
    fallback = {
        "rationale": None,
        "supporting_pmids": cell.get("supporting_pmids", []),
        "supporting_nct_ids": cell.get("supporting_nct_ids", []),
    }

    parsed = _synthesize(_SYNTHESIS_PROMPT, cell, abstracts, trial_summaries, persona)
    if not parsed:
        return fallback

    return {
        "rationale": parsed.get("rationale"),
        "supporting_pmids": parsed.get("supporting_pmids") or fallback["supporting_pmids"],
        "supporting_nct_ids": parsed.get("supporting_nct_ids") or fallback["supporting_nct_ids"],
    }


def generate_failure_analysis(
    cell: dict,
    abstracts: list[str],
    trial_summaries: list[str],
    persona: str = DEFAULT_PERSONA,
) -> dict:
    """
    Explain why previous attempts at this mechanism-indication pair failed.

    Returns dict with keys: summary (str | None), failure_points (list of
    {reason, category, citations}).

    An empty failure_points list is a legitimate result, not an error: stated
    stop reasons are often absent or uninformative ("Business Reasons"), and the
    prompt requires saying so rather than inventing a scientific explanation.
    """
    fallback = {"summary": None, "failure_points": []}

    parsed = _synthesize(_FAILURE_PROMPT, cell, abstracts, trial_summaries, persona)
    if not parsed:
        return fallback

    return {
        "summary": parsed.get("summary"),
        "failure_points": _clean_failure_points(parsed.get("failure_points")),
    }


BRIEFING_SECTIONS = ("clinical_state", "standard_of_care", "momentum", "bottlenecks")


def generate_executive_briefing(
    indication: str,
    context: str,
    coverage_note: str,
    persona: str = DEFAULT_PERSONA,
) -> dict:
    """Write the opening landscape briefing for a disease.

    Args:
        indication: the disease searched.
        context: aggregated evidence — mechanisms with counts, phase mix,
            publication trend, organisations, and sampled records.
        coverage_note: how much of each corpus the analysis actually saw. Passed
            into the prompt so the model calibrates its confidence: a briefing
            drawn from 1.7% of registered trials must not read like one drawn
            from all of them.

    Returns a dict of the four sections, each str | None. Sections are
    independent so a partial response degrades to a gap rather than nothing.
    """
    empty = {section: None for section in BRIEFING_SECTIONS}

    if not context.strip():
        return empty

    client = _client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY not set — skipping executive briefing")
        return empty

    prompt = (
        _load_prompt(_BRIEFING_PROMPT)
        .replace("{persona_lens}", _load_persona_lens(persona))
        .replace("{coverage_note}", coverage_note)
        .replace("{indication}", indication)
        .replace("{context}", context)
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
        logger.exception("Executive briefing failed for indication=%r", indication)
        return empty

    if not parsed:
        return empty

    return {
        section: (parsed.get(section) or None) for section in BRIEFING_SECTIONS
    }


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _synthesize(
    prompt_path: Path,
    cell: dict,
    abstracts: list[str],
    trial_summaries: list[str],
    persona: str,
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
        .replace("{persona_lens}", _load_persona_lens(persona))
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

    An unrecognised category would break the UI's badge mapping, and silently
    dropping the whole point would lose a real finding — so the reason survives
    and only the category falls back.
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
    """Sources are expected to carry their own PMID/NCT identifier, so they are
    labelled by kind only — numbering them invites the model to cite the
    position ("Publication 1") instead of the ID the prompt asks for."""
    parts = [f"[Publication]\n{text}" for text in abstracts]
    parts += [f"[Trial]\n{text}" for text in trial_summaries]
    return "\n\n".join(parts)


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


def _parse_json_object(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    if not text:
        # Almost always the model exhausting max_tokens on thinking before
        # emitting anything — silent otherwise, and indistinguishable from a
        # genuinely empty answer.
        logger.warning("Synthesis returned no text block (check max_tokens vs thinking)")
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        logger.warning("Could not parse synthesis response as JSON: %r", raw[:200])
        return None


def _load_persona_lens(persona: str) -> str:
    """Load a persona's framing paragraph, falling back to the default.

    The lens only ever adds framing — the shared rules (cite the sources, don't
    overstate, don't use training knowledge) live in the main prompt so a
    persona file cannot drop them.
    """
    name = (persona or "").strip().lower()
    if name not in PERSONAS:
        if name:
            logger.warning("Unknown persona %r — falling back to %s", persona, DEFAULT_PERSONA)
        name = DEFAULT_PERSONA
    try:
        return (_PERSONA_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("Persona lens %r unreadable — continuing without it", name)
        return ""


def _load_prompt(path: Path) -> str:
    """Read a prompt file, stripping the leading '# ...' header comments
    that document the file for repo readers — those aren't meant for the model."""
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
