// Shared shapes for the /api/scan response.
//
// These mirror the Python response in api/index.py — when a field changes there,
// it changes here. Previously MatrixCell was redeclared in three components,
// which meant a backend change could leave two of them silently wrong.

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

export interface MatrixCell {
  mechanism_class: string;
  indication: string;
  trial_count_by_status: Record<string, number>;
  publication_count: number;
  publication_growth_rate: number;
  white_space_score: number;
  has_prior_failure: boolean;
  rationale: string | null;
  supporting_pmids: string[];
  supporting_nct_ids: string[];
  /** Present only on the top few cells per section. */
  context?: CellContext;
}

/**
 * How much of the landscape was actually classified. At a constrained budget
 * this is a fraction, not the whole, and the UI has to say so.
 */
export interface Coverage {
  distinct_drugs: number;
  drugs_attempted: number;
  drugs_classified: number;
  trials_total: number;
  trials_classified: number;
  publications_total: number;
  publications_classified: number;
  extraction_budget: number;
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
  /** The remainder the classification budget didn't reach; null if none. */
  unclassified: { trial_count: number; publication_count: number } | null;
  coverage: Coverage;
  key_organizations: Organization[];
  key_researchers: Researcher[];
  // *_count is the true number of matches; *_analyzed is what was ingested.
  trial_count: number;
  trials_analyzed: number;
  publication_count: number;
  publications_analyzed: number;
  patent_count: number;
  patents_analyzed: number;
}

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
