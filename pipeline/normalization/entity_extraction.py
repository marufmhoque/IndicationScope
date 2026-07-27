"""LLM-based mechanism/target extraction from intervention names and abstracts.

Uses EXTRACTION_MODEL (claude-haiku) for high-volume cheap extraction.
Every extraction retains a pointer to its source NCT ID or PMID.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def extract_mechanism(
    text: str,
    source_id: str,
) -> dict:
    """
    Return {mechanism_class, target, drug_class} for the given text snippet.

    Args:
        text: Intervention name, abstract excerpt, or similar free text.
        source_id: NCT ID or PMID the text came from (retained in output for traceability).

    Returns:
        dict with keys: mechanism_class, target, drug_class, source_id
    """
    # TODO: load extraction prompt from pipeline/synthesis/prompts/extraction_prompt.txt
    # TODO: call anthropic client with EXTRACTION_MODEL
    # TODO: parse JSON response
    logger.debug("extract_mechanism called for source_id=%s (stub)", source_id)
    return {
        "mechanism_class": None,
        "target": None,
        "drug_class": None,
        "source_id": source_id,
    }
