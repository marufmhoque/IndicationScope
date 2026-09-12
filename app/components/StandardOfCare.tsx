import PillarGroup from "./PillarGroup";
import { PHASE_LABELS, PHASE_ORDER, type MatrixCell } from "../lib/types";

interface Props {
  cells: MatrixCell[];
}

/**
 * What the field has actually converged on — the inverse of the white-space view.
 * A gap only means something against the baseline of what is already dominant.
 */
export default function StandardOfCare({ cells }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-400 print:text-black">
        Mechanisms carrying the most clinical activity in the ingested sample, ordered
        by active and late-phase trials. This is the established and contested end of
        the landscape.
      </p>

      <PillarGroup
        cells={cells}
        emptyMessage="No mechanism in the ingested sample carries enough trial activity to characterise a standard of care."
        render={(cell) => <SocRow key={cell.mechanism_class} cell={cell} />}
      />
    </div>
  );
}

function SocRow({ cell }: { cell: MatrixCell }) {
  const counts = cell.trial_count_by_status ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const active = counts.ACTIVE ?? 0;
  const phases = PHASE_ORDER.filter((p) => cell.phase_counts?.[p]);
  // Phase 4 is post-marketing study, which is strong evidence a drug is
  // approved — but ClinicalTrials.gov carries no approval status, so this is
  // labelled for what it is and never asserted as approval.
  const postMarketing = cell.phase_counts?.PHASE4 ?? 0;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 break-inside-avoid print:border-gray-300 print:bg-white">
      <div className="flex items-start justify-between gap-4">
        <p className="font-semibold text-white print:text-black">
          {cell.mechanism_class}
        </p>
        {postMarketing > 0 && (
          <span className="shrink-0 rounded-full bg-emerald-900 px-2.5 py-0.5 text-[11px] text-emerald-300 print:bg-white print:text-black print:border print:border-gray-400">
            {postMarketing} post-marketing
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-400">
        <span>
          <span className="font-medium text-gray-200 print:text-black">{total}</span>{" "}
          {total === 1 ? "trial" : "trials"}
        </span>
        <span>
          <span className="font-medium text-gray-200 print:text-black">{active}</span>{" "}
          active
        </span>
        <span>
          <span className="font-medium text-gray-200 print:text-black">
            {cell.literature_support}
          </span>{" "}
          supporting abstracts
        </span>
      </div>

      {phases.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {phases.map((p) => (
            <span
              key={p}
              className="rounded bg-gray-800 px-2 py-0.5 text-[11px] text-gray-400 print:bg-white print:text-black print:border print:border-gray-300"
            >
              {PHASE_LABELS[p] ?? p}: {cell.phase_counts[p]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
