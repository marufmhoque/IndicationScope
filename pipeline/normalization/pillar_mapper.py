"""Groups mechanisms into broad treatment modalities.

Costs nothing: `entity_extraction` already returns `drug_class` alongside
`mechanism_class` ("gene therapy vector", "bispecific monoclonal antibody",
"small molecule inhibitor", "corticosteroid") and the matrix previously discarded
it. This just reads what is already there.

The pillars are deliberately **modality-based, not therapeutic-area based**, so
the same map serves oncology, psychiatry, ophthalmology and metabolic disease.
Matching is first-match-wins over an ordered list, most specific first, because
real classes overlap — an antibody-drug conjugate is both an antibody and a
conjugate, and the more informative reading wins.

This is a navigation aid, not a taxonomy. Anything unrecognised goes to OTHER
rather than being forced into an ill-fitting bucket.
"""

from __future__ import annotations

OTHER = "Other"

# (pillar, substrings). Ordered: earlier entries win.
_PILLARS: list[tuple[str, tuple[str, ...]]] = [
    (
        "Gene & Cell Therapy",
        (
            "gene therapy", "gene transfer", "gene editing", "gene vector",
            "aav", "adeno-associated", "lentivir", "crispr", "car-t", "car t",
            "cell therapy", "stem cell", "cellular therapy", "vector",
        ),
    ),
    (
        "Nucleic Acid Therapeutics",
        (
            "antisense", "sirna", "rnai", "oligonucleotide", "mrna",
            "aptamer", "micro rna", "microrna",
        ),
    ),
    (
        "Antibodies & Biologics",
        (
            "monoclonal", "bispecific", "antibody", "immunoglobulin",
            "fusion protein", "biologic", "biosimilar", "nanobody",
        ),
    ),
    (
        "Peptides & Conjugates",
        (
            "peptide", "pegylated", "conjugate", "protein therapeutic", "enzyme",
            # Peptide and protein hormones: insulins and incretins are the
            # backbone of metabolic disease and are not small molecules.
            "insulin", "incretin", "glp-1", "glp1", "hormone", "somatostatin",
            "analogue of", "mimetic",
        ),
    ),
    (
        "Immunomodulators",
        (
            "immunomodulat", "immunotherap", "checkpoint", "interleukin",
            "cytokine", "vaccine", "interferon", "corticosteroid",
            "glucocorticoid", "steroid", "immunosuppress", "complement",
        ),
    ),
    (
        "Small Molecules",
        (
            "small molecule", "kinase inhibitor", "tyrosine kinase",
            "chemotherap", "cytotoxic", "alkylating", "antimetabolite",
            "nucleoside", "statin", "antibiotic", "antiviral", "derivative",
            # Named pharmacological classes. drug_class usually reports the
            # class ("SSRI", "thiazolidinedione") rather than the modality, so
            # without these whole therapeutic areas collapse into Other:
            # metabolic and psychiatric drugs are almost entirely small
            # molecules and were landing there wholesale.
            "ssri", "snri", "tricyclic", "maoi", "antidepressant",
            "antipsychotic", "anxiolytic", "hypnotic", "benzodiazepine",
            "anesthetic", "analgesic", "opioid", "stimulant",
            "thiazolidinedione", "glitazone", "meglitinide", "sulfonylurea",
            "biguanide", "gliptin", "flozin", "fibrate", "antidiabetic",
            "diuretic", "beta blocker", "ace inhibitor", "calcium channel",
            "hdac", "parp", "proteasome", "cotransporter", "peptidase",
        ),
    ),
    (
        "Device & Procedural",
        (
            "device", "implant", "laser", "radiation", "radiotherap",
            "photodynamic", "surgical", "surgery", "stimulation", "procedure",
            "phototherap", "brachytherap",
        ),
    ),
    (
        "Behavioural & Supportive",
        (
            "behavioral", "behavioural", "lifestyle", "diet", "exercise",
            "physiotherap", "counsel", "education", "supportive", "placebo",
            "vitamin", "supplement", "nutrition", "probiotic",
        ),
    ),
]

# Last resort. Most therapeutics are small molecules, so a class that names a
# pharmacological action but no modality is far more likely to be one than to be
# anything else — and "Small Molecules" is a more useful answer than "Other".
# It will occasionally mis-bucket an antibody whose drug_class went unrecorded,
# which is the accepted cost of not emptying the map into Other.
_ACTION_WORDS = ("inhibitor", "agonist", "antagonist", "modulator", "blocker")


def assign_pillar(drug_class: str | None, mechanism_class: str | None = None) -> str:
    """Return the treatment pillar for a mechanism.

    `drug_class` is the primary signal because it names the modality directly;
    `mechanism_class` is the fallback, since it often carries the modality too
    ("CAR-T cell therapy", "gene therapy"). Unrecognised classes return OTHER.
    """
    for text in (drug_class, mechanism_class):
        if not text:
            continue
        lowered = text.lower()
        for pillar, keywords in _PILLARS:
            if any(keyword in lowered for keyword in keywords):
                return pillar

    for text in (drug_class, mechanism_class):
        if text and any(word in text.lower() for word in _ACTION_WORDS):
            return "Small Molecules"

    return OTHER


def pillar_order() -> list[str]:
    """Stable display order, with OTHER last."""
    return [name for name, _ in _PILLARS] + [OTHER]
