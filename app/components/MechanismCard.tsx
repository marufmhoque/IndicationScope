import { PHASE_LABELS, PHASE_ORDER, type MatrixCell } from "../lib/types";

interface Props {
  cell: MatrixCell;
}

/** One mechanism class, described by what the trial record and literature contain. */
export default function MechanismCard({ cell }: Props) {
  const counts = cell.trial_count_by_status ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const active = counts.ACTIVE ?? 0;
  const phases = PHASE_ORDER.filter((p) => cell.phase_counts?.[p]);
  // Phase 4 is post-marketing study. ClinicalTrials.gov carries no approval
  // status, so this is labelled for what it is and never presented as approval.
  const postMarketing = cell.phase_counts?.PHASE4 ?? 0;

  // A summary is generated on demand after the scan, so "not yet" and "not
  // possible" are different states and the card must not claim the wrong one.
  const summaryPossible =
    !!cell.context &&
    (cell.context.abstracts.length > 0 || cell.context.trial_summaries.length > 0);

  return (
    <div className="space-y-3 rounded-xl border border-gray-800 bg-gray-900 p-5 break-inside-avoid print:border-gray-300 print:bg-white">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-semibold text-white print:text-black">{cell.mechanism_class}</p>
          <p className="mt-0.5 text-xs text-gray-500">
            {[
              cell.target && `Target: ${cell.target}`,
              cell.drug_class && `Class: ${cell.drug_class}`,
            ]
              .filter(Boolean)
              .join(" · ") || "Target not reported"}
          </p>
        </div>
        {postMarketing > 0 && (
          <span className="shrink-0 rounded-full bg-emerald-900 px-2.5 py-0.5 text-[11px] text-emerald-300 print:border print:border-gray-400 print:bg-white print:text-black">
            {postMarketing} post-marketing
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-400">
        <span>
          <span className="font-medium text-gray-200 print:text-black">{total}</span>{" "}
          {total === 1 ? "trial" : "trials"}
        </span>
        <span>
          <span className="font-medium text-gray-200 print:text-black">{active}</span> active
        </span>
        <span>
          <span className="font-medium text-gray-200 print:text-black">
            {cell.literature_support}
          </span>{" "}
          matching abstracts
        </span>
      </div>

      {phases.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {phases.map((p) => (
            <span
              key={p}
              className="rounded bg-gray-800 px-2 py-0.5 text-[11px] text-gray-400 print:border print:border-gray-300 print:bg-white print:text-black"
            >
              {PHASE_LABELS[p] ?? p}: {cell.phase_counts[p]}
            </span>
          ))}
        </div>
      )}

      {cell.rationale ? (
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            Evidence summary
          </p>
          <p className="text-sm leading-relaxed text-gray-300 print:text-black">
            {cell.rationale}
          </p>
        </div>
      ) : summaryPossible ? (
        <p className="text-sm italic text-gray-600">Summarising evidence…</p>
      ) : null}

      {(cell.supporting_pmids.length > 0 || cell.supporting_nct_ids.length > 0) && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {cell.supporting_nct_ids.slice(0, 4).map((id) => (
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
  );
}
