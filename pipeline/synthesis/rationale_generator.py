"""LLM rationale synthesis for top-N white-space candidates.

Uses SYNTHESIS_MODEL (claude-sonnet-4-6). Only fires for the top N cells
(configured via SYNTHESIS_TOP_N) to control cost. Retrieval-augmented only —
the prompt supplies all source material; the model must not draw on training memory.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesis_prompt.txt"


def generate_rationale(cell: dict, abstracts: list[str], trial_summaries: list[str]) -> dict:
    """
    Generate a rationale narrative for a MatrixCell.

    Args:
        cell: MatrixCell dict (mechanism_class, indication, supporting IDs, etc.)
        abstracts: List of relevant PubMed abstract texts (supplied context only).
        trial_summaries: List of relevant CT.gov trial descriptions.

    Returns:
        dict with keys: rationale (str), supporting_pmids (list), supporting_nct_ids (list)
    """
    # TODO: load synthesis prompt from _PROMPT_PATH
    # TODO: build context block from abstracts + trial_summaries
    # TODO: call anthropic client with SYNTHESIS_MODEL
    # TODO: parse response into rationale + cited IDs
    logger.debug(
        "generate_rationale stub — mechanism=%s indication=%s",
        cell.get("mechanism_class"), cell.get("indication"),
    )
    return {
        "rationale": None,
        "supporting_pmids": cell.get("supporting_pmids", []),
        "supporting_nct_ids": cell.get("supporting_nct_ids", []),
    }
