"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, Suspense } from "react";
import KeyPlayers from "../components/KeyPlayers";
import FailureAccordion, {
  canAnalyze,
  fetchFailureAnalysis,
} from "../components/FailureAccordion";
import ExecutiveBriefing from "../components/ExecutiveBriefing";
import MomentumChart from "../components/MomentumChart";
import ClinicalLandscape from "../components/ClinicalLandscape";
import ReportDocument from "../components/ReportDocument";
import ExportDialog from "../components/ExportDialog";
import { PillarStrip } from "../components/PillarGroup";
import { apiUrl } from "../lib/paths";
import type {
  ExecutiveBriefing as Briefing,
  FailureAnalysis,
  ScanResponse,
} from "../lib/types";

type Tab = "landscape" | "attempted" | "players";

function ResultsContent() {
  const params = useSearchParams();
  const router = useRouter();

  const disease = params.get("disease") ?? "";
  const mechanism = params.get("mechanism") ?? undefined;
  const [tab, setTab] = useState<Tab>("landscape");

  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  // The scan stays immutable; synthesis lives beside it keyed by mechanism.
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [summaries, setSummaries] = useState<Record<string, string>>({});
  const [failures, setFailures] = useState<Record<string, FailureAnalysis>>({});
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingStatus, setBriefingStatus] =
    useState<"loading" | "done" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const [exportOpen, setExportOpen] = useState(false);
  const [exportProgress, setExportProgress] = useState<string | null>(null);

  useEffect(() => {
    if (!disease) {
      router.push("/");
      return;
    }

    let cancelled = false;
    setStatus("loading");
    setScan(null);
    setSummaries({});
    setFailures({});
    setBriefing(null);

    fetch(apiUrl("/api/scan"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disease, mechanism: mechanism || null }),
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
  }, [disease, mechanism, router]);

  // The brief is the largest call and does its own background retrieval, so it
  // runs after the scan rather than inside it; the card shows a skeleton meanwhile.
  useEffect(() => {
    if (!scan) return;
    let cancelled = false;
    setBriefingStatus("loading");

    fetch(apiUrl("/api/briefing"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        indication: scan.query.disease,
        context: scan.briefing_context,
        coverage_note: scan.coverage_note,
      }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: Briefing) => {
        if (cancelled) return;
        setBriefing(data);
        setBriefingStatus("done");
      })
      .catch(() => {
        if (!cancelled) setBriefingStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [scan]);

  // Evidence summaries for the leading mechanisms that carry source text.
  useEffect(() => {
    if (!scan) return;
    let cancelled = false;

    scan.mechanisms.forEach((cell) => {
      if (!canAnalyze(cell)) return;
      fetch(apiUrl("/api/rationale"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mechanism_class: cell.mechanism_class,
          indication: scan.query.disease,
          supporting_pmids: cell.supporting_pmids,
          supporting_nct_ids: cell.supporting_nct_ids,
          abstracts: cell.context?.abstracts ?? [],
          trial_summaries: cell.context?.trial_summaries ?? [],
        }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((out) => {
          if (!out?.rationale || cancelled) return;
          setSummaries((prev) => ({ ...prev, [cell.mechanism_class]: out.rationale }));
        })
        .catch(() => {
          /* enrichment only — the card renders without it */
        });
    });

    return () => {
      cancelled = true;
    };
  }, [scan]);

  const recordFailure = useCallback((mechanismClass: string, analysis: FailureAnalysis) => {
    setFailures((prev) => ({ ...prev, [mechanismClass]: analysis }));
  }, []);

  const missingSections = scan
    ? scan.previously_attempted.filter((c) => canAnalyze(c) && !failures[c.mechanism_class])
        .length + (briefingStatus === "done" && briefing ? 0 : 1)
    : 0;

  async function runFullExport() {
    if (!scan) return;
    const pending = scan.previously_attempted.filter(
      (c) => canAnalyze(c) && !failures[c.mechanism_class]
    );

    for (let i = 0; i < pending.length; i++) {
      setExportProgress(`Summarising trial stoppages (${i + 1} of ${pending.length})…`);
      try {
        const data = await fetchFailureAnalysis(pending[i], scan.query.disease);
        if (data) recordFailure(pending[i].mechanism_class, data);
      } catch {
        /* a missing section prints as "not generated" rather than failing the export */
      }
    }

    setExportProgress("Preparing report…");
    // Let the newly generated sections commit before the print snapshot.
    await new Promise((r) => setTimeout(r, 400));
    setExportProgress(null);
    setExportOpen(false);
    window.print();
  }

  function runQuickExport() {
    setExportOpen(false);
    setTimeout(() => window.print(), 100);
  }

  if (!disease) return null;

  return (
    <div className="mx-auto min-h-screen max-w-4xl space-y-8 px-4 py-12 print:max-w-none print:px-0 print:py-0">
      <div className="flex flex-wrap items-start justify-between gap-4 print:hidden">
        <div>
          <button
            onClick={() => router.push("/")}
            className="mb-2 block text-sm text-gray-500 hover:text-gray-300"
          >
            ← New search
          </button>
          <h1 className="text-2xl font-bold text-white">
            {disease}
            {mechanism && (
              <span className="ml-2 text-lg font-normal text-gray-400">· {mechanism}</span>
            )}
          </h1>
        </div>
        {status === "done" && (
          <button
            onClick={() => setExportOpen(true)}
            className="rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 hover:bg-gray-800"
          >
            Download PDF report
          </button>
        )}
      </div>

      {status === "loading" && (
        <div className="space-y-3 print:hidden">
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-indigo-600" />
          </div>
          <p className="text-center text-sm text-gray-500">
            Retrieving trials, literature, and patents…
          </p>
        </div>
      )}

      {status === "error" && (
        <div className="rounded-lg border border-red-800 bg-red-950 p-4 text-sm text-red-300 print:hidden">
          {error ?? "An unexpected error occurred. Please try again."}
        </div>
      )}

      {status === "done" && scan && (
        <>
          <div className="space-y-8 print:hidden">
            <ExecutiveBriefing
              briefing={briefing}
              status={briefingStatus}
              disease={scan.query.disease}
            />

            <SourceCounts scan={scan} />
            <MomentumChart trend={scan.publication_trend} phases={scan.phase_distribution} />

            {scan.mechanisms.length + scan.previously_attempted.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Modalities represented
                </h3>
                <PillarStrip cells={[...scan.mechanisms, ...scan.previously_attempted]} />
              </div>
            )}

            <div>
              <div className="flex gap-1 border-b border-gray-800">
                <TabButton active={tab === "landscape"} onClick={() => setTab("landscape")}>
                  Clinical Landscape <Count>{scan.mechanisms.length}</Count>
                </TabButton>
                <TabButton active={tab === "attempted"} onClick={() => setTab("attempted")}>
                  Previously Attempted <Count>{scan.previously_attempted.length}</Count>
                </TabButton>
                <TabButton active={tab === "players"} onClick={() => setTab("players")}>
                  Key Players{" "}
                  <Count>{scan.key_organizations.length + scan.key_researchers.length}</Count>
                </TabButton>
              </div>
              <p className="mt-3 text-sm text-gray-500">{tabDescription(tab)}</p>
            </div>

            <div>
              {tab === "landscape" && (
                <ClinicalLandscape
                  cells={scan.mechanisms.map((c) => ({
                    ...c,
                    rationale: summaries[c.mechanism_class] ?? null,
                  }))}
                />
              )}
              {tab === "attempted" && (
                <FailureAccordion
                  cells={scan.previously_attempted}
                  indication={scan.query.disease}
                  analyses={failures}
                  onAnalysis={recordFailure}
                />
              )}
              {tab === "players" && (
                <KeyPlayers
                  organizations={scan.key_organizations}
                  researchers={scan.key_researchers}
                />
              )}
            </div>

            <CoverageNote scan={scan} />
          </div>

          <ReportDocument
            scan={scan}
            briefing={briefing}
            rationales={summaries}
            failures={failures}
          />
        </>
      )}

      <ExportDialog
        open={exportOpen}
        missing={missingSections}
        progress={exportProgress}
        onQuick={runQuickExport}
        onFull={runFullExport}
        onClose={() => setExportOpen(false)}
      />
    </div>
  );
}

function tabDescription(tab: Tab): string {
  switch (tab) {
    case "landscape":
      return "Mechanism classes identified in the examined trials and literature, ordered by number of active trials and grouped by treatment modality.";
    case "attempted":
      return "Mechanism classes with at least one trial recorded as terminated or completed with a negative result.";
    case "players":
      return "Trial sponsors, patent assignees and publication authors in the examined records.";
  }
}

/**
 * True totals alongside what was ingested. Coverage ranges from ~2% of registered
 * trials to 100%, so the note states the sample size when it is a small share.
 */
function SourceCounts({ scan }: { scan: ScanResponse }) {
  const trialFraction = scan.sampling.trials.fraction;
  const thin = trialFraction < 0.25;

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
    <div className="space-y-2 border-b border-gray-800 pb-4">
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-400">
        {items.map((i) => (
          <span key={i.label}>
            <span className="font-medium text-white">{i.total.toLocaleString()}</span>{" "}
            {i.label}
            <span className="text-gray-600"> · {i.analyzed.toLocaleString()} examined</span>
          </span>
        ))}
        <span className="ml-auto text-gray-600">
          {new Date(scan.generated_at).toLocaleString()}
        </span>
      </div>

      {thin && (
        <p className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-xs text-amber-300/90">
          The trial data below is drawn from{" "}
          <strong>
            {scan.sampling.trials.ingested.toLocaleString()} of{" "}
            {scan.sampling.trials.total.toLocaleString()}
          </strong>{" "}
          registered trials ({formatPercent(trialFraction)}); counts describe those records,
          not the full registry.
        </p>
      )}
    </div>
  );
}

function CoverageNote({ scan }: { scan: ScanResponse }) {
  const c = scan.coverage;
  const u = scan.unclassified;
  const hasRemainder = !!u && (u.trial_count > 0 || u.publication_count > 0);

  return (
    <div className="space-y-1 rounded-lg border border-gray-800 bg-gray-900/50 p-4 text-xs text-gray-500">
      <p>
        <span className="text-gray-400">Mechanism classification:</span> {c.drugs_classified} of{" "}
        {c.distinct_drugs.toLocaleString()} distinct interventions classified, accounting for{" "}
        {c.trials_classified} of {c.trials_total} examined trials. Matching-abstract counts are
        computed across all {c.abstracts_indexed} examined abstracts.
      </p>
      {hasRemainder && (
        <p>
          <span className="text-gray-400">Not classified:</span> {u!.trial_count} trials and{" "}
          {u!.publication_count} publications — included in the totals above but not attributed
          to a mechanism class.
        </p>
      )}
    </div>
  );
}

function formatPercent(fraction: number): string {
  if (fraction >= 0.995) return "100%";
  if (fraction > 0 && fraction < 0.01) return "under 1%";
  return `${Math.round(fraction * 100)}%`;
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
      className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
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
        <div className="flex min-h-screen items-center justify-center text-gray-500">
          Loading…
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  );
}
