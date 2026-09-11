"use client";

import { useState } from "react";
import { apiUrl } from "../lib/paths";
import type { FailureAnalysis, FailureCategory, MatrixCell } from "../lib/types";

interface Props {
  cells: MatrixCell[];
  indication: string;
  persona: string;
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

type Status = "idle" | "loading" | "done" | "error";

export default function FailureAccordion({ cells, indication, persona }: Props) {
  if (cells.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No mechanisms with prior-failure signals were found in the analyzed sample.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-400">
        Mechanisms with a terminated or negative trial in the record. These are held out
        of the white-space ranking — a mechanism that was already tried and stopped is
        not an untouched opportunity.
      </p>
      {cells.map((cell) => (
        <FailureRow
          key={cell.mechanism_class}
          cell={cell}
          indication={indication}
          persona={persona}
        />
      ))}
    </div>
  );
}

function FailureRow({
  cell,
  indication,
  persona,
}: {
  cell: MatrixCell;
  indication: string;
  persona: string;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [analysis, setAnalysis] = useState<FailureAnalysis | null>(null);

  const trialTotal = Object.values(cell.trial_count_by_status).reduce((a, b) => a + b, 0);
  const canAnalyze =
    !!cell.context &&
    (cell.context.abstracts.length > 0 || cell.context.trial_summaries.length > 0);

  function toggle() {
    const next = !open;
    setOpen(next);
    // Generated on expand, not during the scan: most rows are never opened, and
    // pre-generating every one would spend a model call each for nothing. The
    // persona is re-read here, so re-opening after a lens switch re-synthesizes.
    if (!next || status === "loading" || status === "done" || !canAnalyze) return;

    setStatus("loading");
    fetch(apiUrl("/api/failure-analysis"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mechanism_class: cell.mechanism_class,
        indication,
        persona,
        supporting_pmids: cell.supporting_pmids,
        supporting_nct_ids: cell.supporting_nct_ids,
        abstracts: cell.context?.abstracts ?? [],
        trial_summaries: cell.context?.trial_summaries ?? [],
      }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: FailureAnalysis) => {
        setAnalysis(data);
        setStatus("done");
      })
      .catch(() => setStatus("error"));
  }

  return (
    <div className="rounded-xl border border-amber-900/60 bg-gray-900">
      <button
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-5 py-4 text-left"
      >
        <span className="text-gray-500 text-xs">{open ? "▾" : "▸"}</span>
        <span className="font-semibold text-white">{cell.mechanism_class}</span>
        <span className="ml-auto shrink-0 flex items-center gap-3 text-xs text-gray-400">
          <span>
            {trialTotal} {trialTotal === 1 ? "trial" : "trials"}
          </span>
          <span>{cell.publication_count} pubs</span>
          <span className="rounded-full bg-amber-900 px-2.5 py-0.5 text-amber-300">
            Prior failure
          </span>
        </span>
      </button>

      {open && (
        <div className="border-t border-gray-800 px-5 py-4 space-y-3">
          {status === "loading" && (
            <p className="text-sm text-gray-500">Reviewing the trial record…</p>
          )}

          {status === "error" && (
            <p className="text-sm text-red-400">
              Could not generate the failure analysis. The trial records below are
              unaffected.
            </p>
          )}

          {!canAnalyze && (
            <p className="text-sm text-gray-500">
              No source text was retained for this mechanism, so its failures can&apos;t
              be summarized.
            </p>
          )}

          {status === "done" && analysis && (
            <>
              {analysis.summary && (
                <p className="text-sm text-gray-300 leading-relaxed">{analysis.summary}</p>
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
                      <span className="text-sm text-gray-300">
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
                // A real and common outcome: registry stop reasons are often
                // absent or say only "Business Reasons". Saying so beats
                // inventing a scientific explanation.
                <p className="text-sm text-gray-500 italic">
                  The trial record doesn&apos;t state why these attempts stopped.
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
