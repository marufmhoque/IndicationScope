import CandidateCard from "./CandidateCard";

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
  candidates: MatrixCell[];
  previouslyAttempted: MatrixCell[];
}

export default function ResultsMatrix({ candidates, previouslyAttempted }: Props) {
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-xl font-semibold text-white mb-4">
          White Space Candidates{" "}
          <span className="text-sm font-normal text-gray-500">({candidates.length})</span>
        </h2>
        {candidates.length === 0 ? (
          <p className="text-gray-500 text-sm">No white-space candidates found for this query.</p>
        ) : (
          <div className="grid gap-4">
            {candidates.map((cell, i) => (
              <CandidateCard key={i} cell={cell} variant="candidate" />
            ))}
          </div>
        )}
      </section>

      {previouslyAttempted.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-white mb-2">
            Previously Attempted{" "}
            <span className="text-sm font-normal text-gray-500">({previouslyAttempted.length})</span>
          </h2>
          <p className="text-sm text-amber-600 mb-4">
            These mechanism–indication pairs have prior failure signals. They are excluded from candidates.
          </p>
          <div className="grid gap-4">
            {previouslyAttempted.map((cell, i) => (
              <CandidateCard key={i} cell={cell} variant="attempted" />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
