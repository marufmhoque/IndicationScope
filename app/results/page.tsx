"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import ResultsMatrix from "../components/ResultsMatrix";
import PersonaToggle from "../components/PersonaToggle";
import { apiUrl } from "../lib/paths";

interface CellContext {
  abstracts: string[];
  trial_summaries: string[];
}

interface MatrixCell {
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
  // Present only on the top few candidates — the source text /api/rationale
  // needs, sent back so synthesis doesn't have to re-run ingestion.
  context?: CellContext;
}

interface ScanResponse {
  query: { disease: string; mechanism: string | null; persona: string };
  generated_at: string;
  candidates: MatrixCell[];
  previously_attempted: MatrixCell[];
  // *_count is the true number of matches; *_analyzed is what was actually
  // classified. They differ by orders of magnitude for common diseases.
  trial_count: number;
  trials_analyzed: number;
  publication_count: number;
  publications_analyzed: number;
  patent_count: number;
  patents_analyzed: number;
}

/**
 * Fetch a rationale per candidate and merge each into state as it arrives.
 * Failures are swallowed on purpose: a rationale is enrichment, and the card
 * already renders a "pending synthesis" state without one.
 */
function loadRationales(
  scan: ScanResponse,
  isCancelled: () => boolean,
  setData: React.Dispatch<React.SetStateAction<ScanResponse | null>>,
) {
  scan.candidates.forEach((cell, index) => {
    const ctx = cell.context;
    if (!ctx || (ctx.abstracts.length === 0 && ctx.trial_summaries.length === 0)) return;

    fetch(apiUrl("/api/rationale"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mechanism_class: cell.mechanism_class,
        indication: scan.query.disease,
        supporting_pmids: cell.supporting_pmids,
        supporting_nct_ids: cell.supporting_nct_ids,
        abstracts: ctx.abstracts,
        trial_summaries: ctx.trial_summaries,
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((out) => {
        if (!out?.rationale || isCancelled()) return;
        setData((prev) => {
          if (!prev) return prev;
          const candidates = [...prev.candidates];
          candidates[index] = {
            ...candidates[index],
            rationale: out.rationale,
            supporting_pmids: out.supporting_pmids ?? candidates[index].supporting_pmids,
            supporting_nct_ids: out.supporting_nct_ids ?? candidates[index].supporting_nct_ids,
          };
          return { ...prev, candidates };
        });
      })
      .catch(() => {
        /* enrichment only — leave the card in its pending state */
      });
  });
}

function ResultsContent() {
  const params = useSearchParams();
  const router = useRouter();

  const disease = params.get("disease") ?? "";
  const mechanism = params.get("mechanism") ?? undefined;
  const [persona, setPersona] = useState(params.get("persona") ?? "academic");

  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  const [data, setData] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!disease) {
      router.push("/");
      return;
    }

    // Guards against a superseded query (e.g. a persona switch mid-flight)
    // overwriting newer results — rationale calls in particular run for a while.
    let cancelled = false;

    setStatus("loading");
    fetch(apiUrl("/api/scan"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disease, mechanism: mechanism || null, persona }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`API error ${r.status}`);
        return r.json() as Promise<ScanResponse>;
      })
      .then((json) => {
        if (cancelled) return;
        setData(json);
        setStatus("done");
        // Synthesis is deliberately not part of /api/scan — it would push the
        // request past the serverless function timeout. Cards render without a
        // rationale and fill in as each one lands.
        loadRationales(json, () => cancelled, setData);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(String(e));
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [disease, mechanism, persona, router]);

  if (!disease) return null;

  return (
    <div className="min-h-screen px-4 py-12 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <button
            onClick={() => router.push("/")}
            className="text-sm text-gray-500 hover:text-gray-300 mb-2 block"
          >
            ← New search
          </button>
          <h1 className="text-2xl font-bold text-white">
            {disease}
            {mechanism && (
              <span className="ml-2 text-lg text-gray-400 font-normal">· {mechanism}</span>
            )}
          </h1>
        </div>
        <PersonaToggle value={persona} onChange={setPersona} />
      </div>

      {/* Loading */}
      {status === "loading" && (
        <div className="space-y-3">
          <div className="h-2 w-full rounded-full bg-gray-800 overflow-hidden">
            <div className="h-full bg-indigo-600 rounded-full animate-pulse w-1/2" />
          </div>
          <p className="text-sm text-gray-500 text-center">
            Scanning ClinicalTrials.gov and PubMed…
          </p>
        </div>
      )}

      {/* Error */}
      {status === "error" && (
        <div className="rounded-lg border border-red-800 bg-red-950 p-4 text-red-300 text-sm">
          {error ?? "An unexpected error occurred. Please try again."}
        </div>
      )}

      {/* Results */}
      {status === "done" && data && (
        <>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-400 border-b border-gray-800 pb-4">
            <span>
              <span className="font-medium text-white">
                {data.trial_count.toLocaleString()}
              </span>{" "}
              trials found
              <span className="text-gray-600">
                {" "}
                · {data.trials_analyzed.toLocaleString()} analyzed
              </span>
            </span>
            <span>
              <span className="font-medium text-white">
                {data.publication_count.toLocaleString()}
              </span>{" "}
              publications
              <span className="text-gray-600">
                {" "}
                · {data.publications_analyzed.toLocaleString()} analyzed
              </span>
            </span>
            <span className="ml-auto text-gray-600">
              {new Date(data.generated_at).toLocaleString()}
            </span>
          </div>
          <ResultsMatrix
            candidates={data.candidates}
            previouslyAttempted={data.previously_attempted}
          />
        </>
      )}
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-gray-500">
          Loading…
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  );
}
