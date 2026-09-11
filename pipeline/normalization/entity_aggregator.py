"""Aggregates the organizations and researchers active in a disease landscape.

Deliberately deterministic. Trial sponsors, patent assignees and publication
authors are already structured fields on the source records, so an LLM pass
would add cost and latency and could drop or invent names that are sitting
right there in the metadata.

Name variants are the one real problem ("Regeneron Pharmaceuticals, Inc." vs
"Regeneron"), and that is the same fragmentation already handled for mechanism
labels: group on a canonical key, display the most common raw spelling.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

# Legal and descriptive suffixes that vary between records for the same
# organization. Stripped for grouping only — never for display.
_CORPORATE_NOISE = re.compile(
    r"\b("
    r"inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|"
    r"gmbh|ag|a/s|s\.a|sa|s\.p\.a|nv|n\.v|bv|b\.v|ab|plc|oy|kk|"
    r"pharmaceuticals?|pharma|therapeutics|biosciences?|biotech(nology)?|"
    r"laboratories|labs|holdings?|group|international|worldwide|global"
    r")\b",
    re.IGNORECASE,
)

# Sponsors are a mix of industry and academia. Both are "active organizations",
# but conflating a university with a competitor misreads the landscape, so the
# kind travels with the entity and the UI can split on it.
_ACADEMIC_MARKERS = (
    "university", "universitaire", "universit", "college", "school",
    "hospital", "clinic", "medical cent", "health system", "institute",
    "institut", "foundation", "trust", "nhs", "ministry", "national cent",
    "academy", "academic", "research cent", "cancer cent", "children's",
)

# PubMed affiliations frequently end with a contact email. Author names are
# public academic record; their email addresses are personal contact data the
# analysis has no use for.
_EMAIL = re.compile(r"\S+@\S+\.\S+")


def aggregate_organizations(trials: list[dict], patents: list[dict], limit: int = 15) -> list[dict]:
    """Rank organizations by how much of the landscape they account for.

    Args:
        trials: Normalised trial dicts (uses lead_sponsor).
        patents: Patent records from any patent source (uses assignee).
        limit: How many to return.

    Returns:
        [{name, kind, trial_count, patent_count, total}], most active first.
    """
    spellings: dict[str, Counter] = defaultdict(Counter)
    trial_counts: Counter = Counter()
    patent_counts: Counter = Counter()

    for trial in trials:
        name = (trial.get("lead_sponsor") or "").strip()
        if not name:
            continue
        key = _canonical_org(name)
        if not key:
            continue
        spellings[key][name] += 1
        trial_counts[key] += 1

    for patent in patents:
        name = (patent.get("assignee") or "").strip()
        if not name:
            continue
        key = _canonical_org(name)
        if not key:
            continue
        spellings[key][name] += 1
        patent_counts[key] += 1

    out = []
    for key, variants in spellings.items():
        display = variants.most_common(1)[0][0]
        out.append(
            {
                "name": display,
                "kind": "academic" if _is_academic(display) else "industry",
                "trial_count": trial_counts[key],
                "patent_count": patent_counts[key],
                "total": trial_counts[key] + patent_counts[key],
            }
        )

    out.sort(key=lambda o: (-o["total"], o["name"]))
    return out[:limit]


def aggregate_researchers(publications: list[dict], limit: int = 15) -> list[dict]:
    """Rank authors by publication count across the sampled literature.

    Returns [{name, publication_count, affiliation}], most published first.
    """
    counts: Counter = Counter()
    affiliations: dict[str, Counter] = defaultdict(Counter)

    for pub in publications:
        # A name can legitimately repeat within one paper's author list only by
        # error; count each author once per publication regardless.
        seen: set[str] = set()
        for author in pub.get("authors") or []:
            name = (author.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            counts[key] += 1
            affiliation = _clean_affiliation(author.get("affiliation") or "")
            if affiliation:
                affiliations[key][affiliation] += 1

    display_names: dict[str, str] = {}
    for pub in publications:
        for author in pub.get("authors") or []:
            name = (author.get("name") or "").strip()
            if name:
                display_names.setdefault(name.lower(), name)

    out = [
        {
            "name": display_names.get(key, key),
            "publication_count": count,
            "affiliation": (
                affiliations[key].most_common(1)[0][0] if affiliations[key] else ""
            ),
        }
        for key, count in counts.items()
    ]

    out.sort(key=lambda r: (-r["publication_count"], r["name"]))
    return out[:limit]


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _canonical_org(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[.,]", " ", text)
    text = _CORPORATE_NOISE.sub(" ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_academic(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in _ACADEMIC_MARKERS)


def _clean_affiliation(affiliation: str) -> str:
    """Drop contact emails and trim to the leading institutional clause."""
    text = _EMAIL.sub("", affiliation)
    text = text.split(",")[0].strip(" .;")
    return text[:120]
