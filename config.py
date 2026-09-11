EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
# Sonnet 5 is both cheaper ($2/$10 vs $3/$15 per MTok) and more capable than the
# 4-6 this was pinned to.
SYNTHESIS_MODEL = "claude-sonnet-5"
# Cells per section that carry source text back to the client. Only these can
# have a rationale or failure analysis generated, so it bounds both the
# response size and the number of synthesis calls a scan can lead to.
SYNTHESIS_TOP_N = 5

# Records sent to the LLM for mechanism classification per scan. This is the
# dominant cost of a scan; ingestion depth is nearly free by comparison.
#
# Coverage is better than the raw number suggests: repeated drugs are collapsed
# and classified once, most-frequent first (see matrix_builder), so 60 calls
# covered 40-64% of trials across the diseases measured. Raise this single
# number to buy more coverage.
EXTRACTION_BUDGET = 60

CT_GOV_BASE = "https://clinicaltrials.gov/api/v2/studies"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
