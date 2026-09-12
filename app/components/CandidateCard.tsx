import ScoreLegend from "./ScoreLegend";
import type { MatrixCell } from "../lib/types";

interface Props {
  cell: MatrixCell;
}

export default function CandidateCard({ cell }: Props) {
  const trialTotal = Object.values(cell.trial_count_by_status).reduce((a, b) => a + b, 0);

  // A rationale is generated on demand after the scan, so "no rationale yet" and
  // "no rationale possible" are different states and the card must not claim the
  // wrong one — it previously promised synthesis that was never coming.
  const rationalePossible =
    !!cell.context &&
    (cell.context.abstracts.length > 0 || cell.context.trial_summaries.length > 0);

  return (
    <div className="rounded-xl border border-indigo-800 bg-gray-900 p-5 space-y-3 break-inside-avoid print:border-gray-300 print:bg-white">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Mechanism class</p>
          <p className="font-semibold text-white print:text-black">
            {cell.mechanism_class || "—"}
          </p>
          {cell.drug_class && (
            <p className="text-xs text-gray-500 mt-0.5">{cell.drug_class}</p>
          )}
        </div>
        <ScoreLegend
          score={cell.white_space_score}
          components={cell.score_components}
        />
      </div>

      <div className="flex gap-6 text-sm text-gray-400">
        <span>
          <span className="font-medium text-gray-200 print:text-black">
            {cell.literature_support}
          </span>{" "}
          supporting abstracts
        </span>
        <span>
          <span className="font-medium text-gray-200">{trialTotal}</span>{" "}
          {trialTotal === 1 ? "trial" : "trials"}
        </span>
      </div>

      {cell.rationale ? (
        <p className="text-sm text-gray-300 leading-relaxed">{cell.rationale}</p>
      ) : rationalePossible ? (
        <p className="text-sm text-gray-600 italic">Synthesizing rationale…</p>
      ) : (
        <p className="text-sm text-gray-600 italic">
          Not enough source text was retained to synthesize a rationale.
        </p>
      )}

      {(cell.supporting_pmids.length > 0 || cell.supporting_nct_ids.length > 0) && (
        <div className="flex flex-wrap gap-1.5 pt-1">
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
        </div>
      )}
    </div>
  );
}
