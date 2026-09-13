// Shared shapes for the /api/scan response.
//
// These mirror the Python response in api/index.py — when a field changes there,
// it changes here, so a backend change can't leave a component silently wrong.

/** Source text a cell carries so synthesis can run without re-ingesting. */
export interface CellContext {
  abstracts: string[];
  trial_summaries: string[];
}

export interface MatrixCell {
  mechanism_class: string;
  indication: string;
  trial_count_by_status: Record<string, number>;
  phase_counts: Record<string, number>;
  drug_class: string | null;
  /** Molecular target reported for the mechanism's agents. */
  target: string | null;
  /** Treatment modality, derived from drug_class. */
  pillar: string | null;
  publication_count: number;
  /** Abstracts matching this mechanism across the whole sample. */
  literature_support: number;
  has_prior_failure: boolean;
  /** Evidence summary text (API key kept as "rationale"). */
  rationale: string | null;
  supporting_pmids: string[];
  supporting_nct_ids: string[];
  /** Present only on the leading cells of each list. */
  context?: CellContext;
}

/** How much of the ingested corpus was classified. */
export interface Coverage {
  distinct_drugs: number;
  drugs_attempted: number;
  drugs_classified: number;
  trials_total: number;
  trials_classified: number;
  publications_total: number;
  publications_classified: number;
  abstracts_indexed: number;
  extraction_budget: number;
}

/**
 * How much of each corpus was ingested at all. Ranges from ~2% (type 2
 * diabetes) to 100% (rare indications).
 */
export interface SourceSampling {
  ingested: number;
  total: number;
  fraction: number;
}

export interface Sampling {
  trials: SourceSampling;
  publications: SourceSampling;
}

/**
 * Counts sum to more than `total_trials`: a PHASE1|PHASE2 trial lands in both
 * buckets, so the totals travel alongside rather than being inferred.
 */
export interface PhaseDistribution {
  counts: Record<string, number>;
  phased_trials: number;
  total_trials: number;
}

export interface PublicationTrend {
  years: Record<string, number>;
  /** Always incomplete; never plotted as a decline. */
  partial_year: number;
}

export interface Organization {
  name: string;
  kind: "industry" | "academic";
  trial_count: number;
  patent_count: number;
  total: number;
}

export interface Researcher {
  name: string;
  publication_count: number;
  affiliation: string;
}

export interface ScanResponse {
  query: { disease: string; mechanism: string | null };
  generated_at: string;
  /** Classified mechanisms without a recorded terminated/negative trial, by activity. */
  mechanisms: MatrixCell[];
  /** Classified mechanisms with at least one terminated/negative trial, by activity. */
  previously_attempted: MatrixCell[];
  unclassified: { trial_count: number; publication_count: number } | null;
  coverage: Coverage;
  sampling: Sampling;
  phase_distribution: PhaseDistribution;
  publication_trend: PublicationTrend;
  key_organizations: Organization[];
  key_researchers: Researcher[];
  /** Aggregated evidence posted back to /api/briefing. */
  briefing_context: string;
  coverage_note: string;
  trial_count: number;
  trials_analyzed: number;
  publication_count: number;
  publications_analyzed: number;
  patent_count: number;
  patents_analyzed: number;
}

export type BriefingSectionKey =
  | "disease_overview"
  | "molecular_mechanisms"
  | "epidemiology"
  | "standard_of_treatment"
  | "current_research"
  | "historical_failures";

/** A background abstract retrieved for the brief's overview, epidemiology or cost sections. */
export interface BriefingReference {
  pmid: string;
  title: string;
  facet: "overview" | "epidemiology" | "cost" | string;
}

export type ExecutiveBriefing = Record<BriefingSectionKey, string | null> & {
  references?: BriefingReference[];
};

export const BRIEFING_SECTIONS: { key: BriefingSectionKey; label: string }[] = [
  { key: "disease_overview", label: "Disease Overview & Symptoms" },
  { key: "molecular_mechanisms", label: "Molecular Mechanisms & Affected Proteins" },
  { key: "epidemiology", label: "Disease Population & Epidemiology" },
  { key: "standard_of_treatment", label: "Current Standard of Treatment" },
  { key: "current_research", label: "Clinical Research Currently Being Conducted" },
  { key: "historical_failures", label: "Historical Context of Trial Failures" },
];

export const FAILURE_CATEGORIES = [
  "safety",
  "efficacy",
  "enrolment",
  "business",
  "unknown",
] as const;

export type FailureCategory = (typeof FAILURE_CATEGORIES)[number];

export interface FailurePoint {
  reason: string;
  category: FailureCategory;
  citations: string[];
}

export interface FailureAnalysis {
  summary: string | null;
  failure_points: FailurePoint[];
}

/** Human-readable phase labels. UNSPECIFIED covers observational studies. */
export const PHASE_LABELS: Record<string, string> = {
  EARLY_PHASE1: "Early Phase 1",
  PHASE1: "Phase 1",
  PHASE2: "Phase 2",
  PHASE3: "Phase 3",
  PHASE4: "Phase 4",
  NA: "Not applicable",
  UNSPECIFIED: "No phase listed",
};

export const PHASE_ORDER = [
  "EARLY_PHASE1",
  "PHASE1",
  "PHASE2",
  "PHASE3",
  "PHASE4",
  "NA",
  "UNSPECIFIED",
];
