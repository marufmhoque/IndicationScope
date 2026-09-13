"use client";

import { useState } from "react";
import { apiUrl } from "../lib/paths";
import type { FailureAnalysis, FailureCategory, MatrixCell } from "../lib/types";

interface Props {
  cells: MatrixCell[];
  indication: string;
  /** Owned by the page so the exported report can include them. */
  analyses: Record<string, FailureAnalysis>;
  onAnalysis: (mechanism: string, analysis: FailureAnalysis) => void;
}

const CATEGORY_STYLES: Record<FailureCategory, string> = {
  safety: "bg-red-950 text-red-300 border-red-900",
  efficacy: "bg-amber-950 text-amber-300 border-amber-900",
  enrolment: "bg-sky-950 text-sky-300 border-sky-900",
  business: "bg-gray-800 text-gray-300 border-gray-700",
  unknown: "bg-gray-800 text-gray-400 border-gray-700",
};

const CATEGORY_LABELS: Record<FailureCategory, string> = {
  safety: "Safety",
  efficacy: "Efficacy",
  enrolment: "Enrolment",
  business: "Business",
  unknown: "Not stated",
};

export function canAnalyze(cell: MatrixCell): boolean {
  return (
    !!cell.context &&
    (cell.context.abstracts.length > 0 || cell.context.trial_summaries.length > 0)
  );
}

export async function fetchFailureAnalysis(
  cell: MatrixCell,
  indication: string
): Promise<FailureAnalysis | null> {
  const res = await fetch(apiUrl("/api/failure-analysis"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mechanism_class: cell.mechanism_class,
      indication,
      supporting_pmids: cell.supporting_pmids,
      supporting_nct_ids: cell.supporting_nct_ids,
      abstracts: cell.context?.abstracts ?? [],
      trial_summaries: cell.context?.trial_summaries ?? [],
    }),
  });
  return res.ok ? ((await res.json()) as FailureAnalysis) : null;
}

export default function FailureAccordion({ cells, indication, analyses, onAnalysis }: Props) {
  if (cells.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No mechanism class in the examined trials has a trial recorded as terminated or
        completed with a negative result.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-400 print:text-black">
        Mechanism classes with at least one trial recorded as terminated or completed with
        a negative result. Expanding a row summarises the reasons stated in the trial
        registry and supporting publications.
      </p>
      {cells.map((cell) => (
        <FailureRow
          key={cell.mechanism_class}
          cell={cell}
          indication={indication}
          analysis={analyses[cell.mechanism_class]}
          onAnalysis={onAnalysis}
        />
      ))}
    </div>
  );
}

function FailureRow({
  cell,
  indication,
  analysis,
  onAnalysis,
}: {
  cell: MatrixCell;
  indication: string;
  analysis?: FailureAnalysis;
  onAnalysis: (mechanism: string, analysis: FailureAnalysis) => void;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const trialTotal = Object.values(cell.trial_count_by_status).reduce((a, b) => a + b, 0);
  const analyzable = canAnalyze(cell);

  function toggle() {
    const next = !open;
    setOpen(next);
    // Generated on expand, not during the scan: most rows are never opened.
    if (!next || loading || analysis || !analyzable) return;

    setLoading(true);
    setFailed(false);
    fetchFailureAnalysis(cell, indication)
      .then((data) => {
        if (data) onAnalysis(cell.mechanism_class, data);
        else setFailed(true);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 break-inside-avoid print:border-gray-300 print:bg-white">
      <button
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-5 py-4 text-left"
      >
        <span className="text-xs text-gray-500">{open ? "▾" : "▸"}</span>
        <span className="font-semibold text-white print:text-black">{cell.mechanism_class}</span>
        <span className="ml-auto flex shrink-0 items-center gap-3 text-xs text-gray-400">
          <span>
            {trialTotal} {trialTotal === 1 ? "trial" : "trials"}
          </span>
          <span>{cell.literature_support} abstracts</span>
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-gray-800 px-5 py-4">
          {loading && <p className="text-sm text-gray-500">Reviewing the trial record…</p>}

          {failed && (
            <p className="text-sm text-red-400">
              The summary could not be generated. The trial records below are unaffected.
            </p>
          )}

          {!analyzable && (
            <p className="text-sm text-gray-500">
              No source text was retained for this mechanism class.
            </p>
          )}

          {analysis && (
            <>
              {analysis.summary && (
                <p className="text-sm leading-relaxed text-gray-300 print:text-black">
                  {analysis.summary}
                </p>
              )}

              {analysis.failure_points.length > 0 ? (
                <ul className="space-y-2.5">
                  {analysis.failure_points.map((point, i) => (
                    <li key={i} className="flex gap-3">
                      <span
                        className={`mt-0.5 h-fit shrink-0 rounded border px-2 py-0.5 text-[11px] font-medium ${
                          CATEGORY_STYLES[point.category] ?? CATEGORY_STYLES.unknown
                        }`}
                      >
                        {CATEGORY_LABELS[point.category] ?? CATEGORY_LABELS.unknown}
                      </span>
                      <span className="text-sm text-gray-300 print:text-black">
                        {point.reason}
                        {point.citations.length > 0 && (
                          <span className="ml-2 text-xs text-gray-500">
                            {point.citations.join(" · ")}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                // Registry stop reasons are frequently absent or administrative.
                <p className="text-sm italic text-gray-500">
                  The trial record does not state why these trials stopped.
                </p>
              )}
            </>
          )}

          {(cell.supporting_nct_ids.length > 0 || cell.supporting_pmids.length > 0) && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {cell.supporting_nct_ids.slice(0, 6).map((id) => (
                <a
                  key={id}
                  href={`https://clinicaltrials.gov/study/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400 hover:text-gray-200"
                >
                  {id}
                </a>
              ))}
              {cell.supporting_pmids.slice(0, 4).map((id) => (
                <a
                  key={id}
                  href={`https://pubmed.ncbi.nlm.nih.gov/${id}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400 hover:text-gray-200"
                >
                  PMID:{id}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
