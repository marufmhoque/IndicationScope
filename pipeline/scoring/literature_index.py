"""Deterministic literature attribution over the sampled abstracts.

The LLM classification path attributes publications to mechanisms, but it only
reaches ~21 abstracts per scan and most of those name no mechanism at all —
measured, 185/198 unclassified for progeria, 197/200 for pancreatic cancer. The
resulting per-cell counts are 0-3 for every disease tested, which is too sparse
to rank on.

This indexes all ~200 sampled abstracts instead, with no model calls, by matching
a mechanism's distinctive words against them.

"Distinctive" is decided by the corpus, not by a hardcoded list, which is what
makes this work for any disease. A token appearing in most abstracts carries no
information about a particular mechanism: "gene" occurs in 96% of wet-AMD
abstracts and 70% of progeria ones, while "vegf" (38% / 1%) and "progerin"
(0% / 36%) each discriminate in exactly one of them.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# Above this document frequency a token is treated as corpus boilerplate.
_DF_CEILING = 0.50

# Shorter tokens ("il", "a", "6") match far too much on their own.
_MIN_TOKEN_LEN = 3

# Pharmacological role words. These are meaningful inside a label but useless as
# search anchors — nearly every mechanism is an "inhibitor" of something, so
# matching on the role rather than the target finds the whole corpus.
_ROLE_WORDS = frozenset(
    {
        "inhibitor", "inhibitors", "antagonist", "antagonists", "agonist",
        "agonists", "receptor", "receptors", "therapy", "therapies", "agent",
        "agents", "modulator", "modulators", "drug", "drugs", "treatment",
        "treatments", "blocker", "blockers", "analog", "analogue", "class",
        "targeting", "targeted", "selective", "based", "and", "the", "for",
        "with", "anti",
    }
)

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


class LiteratureIndex:
    """Counts how many sampled abstracts support each mechanism label."""

    def __init__(self, publications: list[dict]):
        self._docs: list[set[str]] = [
            self._tokenize(f"{p.get('title', '')} {p.get('abstract', '')}")
            for p in publications
        ]
        self._total = len(self._docs)

        counts: Counter = Counter()
        for doc in self._docs:
            counts.update(doc)

        # Tokens that survive the corpus's own boilerplate threshold.
        self._df: dict[str, float] = (
            {tok: n / self._total for tok, n in counts.items()} if self._total else {}
        )

    def support(self, label: str) -> int:
        """Number of sampled abstracts matching every distinctive token of `label`.

        Returns 0 when nothing distinctive survives — which is a real answer, not
        a failure: it means the label is indistinguishable from this corpus's
        background vocabulary, so it has earned no literature credit.
        """
        anchors = self.anchors(label)
        if not anchors:
            return 0
        return sum(1 for doc in self._docs if anchors <= doc)

    def anchors(self, label: str) -> set[str]:
        """The distinctive tokens of a label, after role-word and DF filtering."""
        return {
            tok
            for tok in self._tokenize(label)
            if tok not in _ROLE_WORDS
            and len(tok) >= _MIN_TOKEN_LEN
            and self._df.get(tok, 0.0) <= _DF_CEILING
        }

    @property
    def document_count(self) -> int:
        return self._total

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {tok for tok in _TOKEN_RE.split(text.lower()) if tok}
