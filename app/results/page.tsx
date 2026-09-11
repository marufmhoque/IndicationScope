"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, Suspense } from "react";
import ResultsMatrix from "../components/ResultsMatrix";
import PersonaToggle from "../components/PersonaToggle";
import KeyPlayers from "../components/KeyPlayers";
import FailureAccordion from "../components/FailureAccordion";
import { apiUrl } from "../lib/paths";
import type { ScanResponse } from "../lib/types";

type Tab = "whitespace" | "attempted" | "players";

function ResultsContent() {
  const params = useSearchParams();
  const router = useRouter();

  const disease = params.get("disease") ?? "";
  const mechanism = params.get("mechanism") ?? undefined;
  const [persona, setPersona] = useState(params.get("persona") ?? "academic");
  const [tab, setTab] = useState<Tab>("whitespace");

  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  // The scan is kept immutable and rationales live beside it, keyed by
  // mechanism. Merging synthesis back into the scan meant a persona switch had
  // to surgically undo it; this way switching just clears a map.
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [rationales, setRationales] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  // Persona is deliberately NOT a dependency here. It only reframes synthesis,
  // so re-ingesting on a lens switch would re-run every source fetch and every
  // classification to arrive at exactly the same evidence.
  useEffect(() => {
    if (!disease) {
      router.push("/");
      return;
    }

    let cancelled = false;
    setStatus("loading");
    setScan(null);
    setRationales({});

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
        setScan(json);
        setStatus("done");
      })
      .catch((e) => {
        if (cancelled) return;
        setError(String(e));
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disease, mechanism, router]);

  // Synthesis runs after the scan, and again on a lens switch. It is separate
  // from /api/scan because it is the most expensive step and would otherwise
  // push a scan past the serverless function timeout.
  useEffect(() => {
    if (!scan) return;

    let cancelled = false;
    setRationales({});

    scan.candidates.forEach((cell) => {
      const ctx = cell.context;
      if (!ctx || (ctx.abstracts.length === 0 && ctx.trial_summaries.length === 0)) return;

      fetch(apiUrl("/api/rationale"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mechanism_class: cell.mechanism_class,
          indication: scan.query.disease,
          persona,
          supporting_pmids: cell.supporting_pmids,
          supporting_nct_ids: cell.supporting_nct_ids,
          abstracts: ctx.abstracts,
          trial_summaries: ctx.trial_summaries,
        }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((out) => {
          if (!out?.rationale || cancelled) return;
          setRationales((prev) => ({ ...prev, [cell.mechanism_class]: out.rationale }));
        })
        .catch(() => {
          /* enrichment only — the card renders without it */
        });
    });

    return () => {
      cancelled = true;
    };
  }, [scan, persona]);

  const newSearch = useCallback(() => router.push("/"), [router]);

  if (!disease) return null;

  return (
    <div className="min-h-screen px-4 py-12 max-w-4xl mx-auto space-y-8">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <button
            onClick={newSearch}
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

      {status === "loading" && (
        <div className="space-y-3">
          <div className="h-2 w-full rounded-full bg-gray-800 overflow-hidden">
            <div className="h-full bg-indigo-600 rounded-full animate-pulse w-1/2" />
          </div>
          <p className="text-sm text-gray-500 text-center">
            Scanning trials, literature, and patents…
          </p>
        </div>
      )}

      {status === "error" && (
        <div className="rounded-lg border border-red-800 bg-red-950 p-4 text-red-300 text-sm">
          {error ?? "An unexpected error occurred. Please try again."}
        </div>
      )}

      {status === "done" && scan && (
        <>
          <SourceCounts scan={scan} />

          <div className="flex gap-1 border-b border-gray-800">
            <TabButton active={tab === "whitespace"} onClick={() => setTab("whitespace")}>
              White Space <Count>{scan.candidates.length}</Count>
            </TabButton>
            <TabButton active={tab === "attempted"} onClick={() => setTab("attempted")}>
              Previously Attempted <Count>{scan.previously_attempted.length}</Count>
            </TabButton>
            <TabButton active={tab === "players"} onClick={() => setTab("players")}>
              Key Players{" "}
              <Count>{scan.key_organizations.length + scan.key_researchers.length}</Count>
            </TabButton>
          </div>

          {tab === "whitespace" && (
            <ResultsMatrix
              candidates={scan.candidates.map((c) => ({
                ...c,
                rationale: rationales[c.mechanism_class] ?? null,
              }))}
            />
          )}

          {tab === "attempted" && (
            <FailureAccordion
              cells={scan.previously_attempted}
              indication={scan.query.disease}
              persona={persona}
            />
          )}

          {tab === "players" && (
            <KeyPlayers
              organizations={scan.key_organizations}
              researchers={scan.key_researchers}
            />
          )}

          <CoverageNote scan={scan} />
        </>
      )}
    </div>
  );
}

/**
 * True match totals alongside what was actually ingested. Showing only the
 * total would imply the analysis covered all of it.
 */
function SourceCounts({ scan }: { scan: ScanResponse }) {
  const items = [
    { label: "trials", total: scan.trial_count, analyzed: scan.trials_analyzed },
    {
      label: "publications",
      total: scan.publication_count,
      analyzed: scan.publications_analyzed,
    },
    { label: "patents", total: scan.patent_count, analyzed: scan.patents_analyzed },
  ];

  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-400 border-b border-gray-800 pb-4">
      {items.map((i) => (
        <span key={i.label}>
          <span className="font-medium text-white">{i.total.toLocaleString()}</span>{" "}
          {i.label}
          <span className="text-gray-600"> · {i.analyzed.toLocaleString()} ingested</span>
        </span>
      ))}
      <span className="ml-auto text-gray-600">
        {new Date(scan.generated_at).toLocaleString()}
      </span>
    </div>
  );
}

/**
 * How much of the ingested sample was actually classified. At a constrained
 * budget this is a fraction, and omitting it would present partial mechanism
 * coverage as a complete landscape.
 */
function CoverageNote({ scan }: { scan: ScanResponse }) {
  const c = scan.coverage;
  const unclassified = scan.unclassified;
  const hasRemainder =
    !!unclassified && (unclassified.trial_count > 0 || unclassified.publication_count > 0);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 text-xs text-gray-500 space-y-1">
      <p>
        <span className="text-gray-400">Mechanism coverage:</span> {c.drugs_classified} of{" "}
        {c.distinct_drugs.toLocaleString()} distinct interventions classified, accounting
        for {c.trials_classified} of {c.trials_total} ingested trials.
      </p>
      {hasRemainder && (
        <p>
          <span className="text-gray-400">Not yet classified:</span>{" "}
          {unclassified!.trial_count} trials and {unclassified!.publication_count}{" "}
          publications. These count toward the totals above but aren&apos;t attributed to
          a mechanism, so they are not ranked.
        </p>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
        active
          ? "border-indigo-500 text-white"
          : "border-transparent text-gray-500 hover:text-gray-300"
      }`}
    >
      {children}
    </button>
  );
}

function Count({ children }: { children: React.ReactNode }) {
  return <span className="ml-1 text-xs text-gray-600">({children})</span>;
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
