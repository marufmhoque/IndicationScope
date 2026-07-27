"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import ResultsMatrix from "../components/ResultsMatrix";
import PersonaToggle from "../components/PersonaToggle";

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
}

interface ScanResponse {
  query: { disease: string; mechanism: string | null; persona: string };
  generated_at: string;
  candidates: MatrixCell[];
  previously_attempted: MatrixCell[];
  trial_count: number;
  publication_count: number;
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

    setStatus("loading");
    fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disease, mechanism: mechanism || null, persona }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`API error ${r.status}`);
        return r.json() as Promise<ScanResponse>;
      })
      .then((json) => {
        setData(json);
        setStatus("done");
      })
      .catch((e) => {
        setError(String(e));
        setStatus("error");
      });
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
            Scanning ClinicalTrials.gov and PubMed… this may take up to 2 minutes.
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
          <div className="flex gap-6 text-sm text-gray-400 border-b border-gray-800 pb-4">
            <span>
              <span className="font-medium text-white">{data.trial_count}</span> trials indexed
            </span>
            <span>
              <span className="font-medium text-white">{data.publication_count}</span> publications
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
