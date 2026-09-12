// Shared shapes for the /api/scan response.
//
// These mirror the Python response in api/index.py — when a field changes there,
// it changes here. MatrixCell was once redeclared in three components, which
// meant a backend change could leave two of them silently wrong.

export const PERSONAS = [
  {
    value: "academic",
    label: "Academic",
    blurb: "Biology and pathway rationale; where the literature clusters.",
  },
  {
    value: "startup",
    label: "Startup",
    blurb: "Competitive density, unclaimed space, patent position.",
  },
  {
    value: "diligence",
    label: "Due Diligence",
    blurb: "Risk first: safety signals, prior failures, evidence quality.",
  },
] as const;

export type Persona = (typeof PERSONAS)[number]["value"];

/** Source text a cell carries so synthesis can run without re-ingesting. */
export interface CellContext {
  abstracts: string[];
  trial_summaries: string[];
}

/** Why a cell scored what it did — shown in the score legend. */
export interface ScoreComponents {
  literature_support: number;
  max_support: number;
  evidence: number;
  openness: number;
  active_trials: number;
  total_trials: number;
  failure_penalty: number;
}

export interface MatrixCell {
  mechanism_class: string;
  indication: string;
  trial_count_by_status: Record<string, number>;
  phase_counts: Record<string, number>;
  drug_class: string | null;
  /** Treatment modality, derived from drug_class. */
  pillar: string | null;
  publication_count: number;
  /** Abstracts matching this mechanism across the whole sample. */
  literature_support: number;
  recent_publication_share: number;
  white_space_score: number;
  score_components?: ScoreComponents;
  has_prior_failure: boolean;
  rationale: string | null;
  supporting_pmids: string[];
  supporting_nct_ids: string[];
  /** Present only on the top few cells per section. */
  context?: CellContext;
}

/** How much of the corpus was classified, once ingested. */
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
 * diabetes) to 100% (rare indications) — the difference the UI must convey.
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
  query: { disease: string; mechanism: string | null; persona: string };
  generated_at: string;
  candidates: MatrixCell[];
  previously_attempted: MatrixCell[];
  standard_of_care: MatrixCell[];
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

export interface ExecutiveBriefing {
  clinical_state: string | null;
  standard_of_care: string | null;
  momentum: string | null;
  bottlenecks: string | null;
}

export const BRIEFING_SECTIONS: {
  key: keyof ExecutiveBriefing;
  label: string;
}[] = [
  { key: "clinical_state", label: "Clinical state" },
  { key: "standard_of_care", label: "Standard of care" },
  { key: "momentum", label: "Where momentum is moving" },
  { key: "bottlenecks", label: "Pipeline bottlenecks" },
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
