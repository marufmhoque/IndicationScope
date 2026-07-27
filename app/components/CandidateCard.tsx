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

interface Props {
  cell: MatrixCell;
  variant?: "candidate" | "attempted";
}

export default function CandidateCard({ cell, variant = "candidate" }: Props) {
  const borderColor = variant === "candidate" ? "border-indigo-800" : "border-amber-800";
  const badgeColor =
    variant === "candidate"
      ? "bg-indigo-900 text-indigo-300"
      : "bg-amber-900 text-amber-300";
  const scorePercent = Math.round(cell.white_space_score * 100);

  return (
    <div className={`rounded-xl border ${borderColor} bg-gray-900 p-5 space-y-3`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Mechanism class</p>
          <p className="font-semibold text-white">{cell.mechanism_class || "—"}</p>
        </div>
        {variant === "candidate" && (
          <div className="shrink-0 text-right">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Score</p>
            <p className="text-2xl font-bold text-indigo-400">{scorePercent}</p>
          </div>
        )}
        {variant === "attempted" && (
          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${badgeColor}`}>
            Prior failure
          </span>
        )}
      </div>

      <div className="flex gap-6 text-sm text-gray-400">
        <span>
          <span className="font-medium text-gray-200">{cell.publication_count}</span> publications
        </span>
        <span>
          <span className="font-medium text-gray-200">
            {Object.values(cell.trial_count_by_status).reduce((a, b) => a + b, 0)}
          </span>{" "}
          trials
        </span>
      </div>

      {cell.rationale ? (
        <p className="text-sm text-gray-300 leading-relaxed">{cell.rationale}</p>
      ) : (
        <p className="text-sm text-gray-600 italic">Rationale pending synthesis…</p>
      )}

      {(cell.supporting_pmids.length > 0 || cell.supporting_nct_ids.length > 0) && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {cell.supporting_pmids.slice(0, 4).map((id) => (
            <span key={id} className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
              PMID:{id}
            </span>
          ))}
          {cell.supporting_nct_ids.slice(0, 4).map((id) => (
            <span key={id} className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
              {id}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
