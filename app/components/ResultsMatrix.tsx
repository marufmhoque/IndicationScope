import CandidateCard from "./CandidateCard";
import type { MatrixCell } from "../lib/types";

interface Props {
  candidates: MatrixCell[];
}

export default function ResultsMatrix({ candidates }: Props) {
  if (candidates.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No white-space candidates were identified in the analyzed sample. Mechanisms with
        prior failures are listed under Previously Attempted.
      </p>
    );
  }

  return (
    <div className="grid gap-4">
      {candidates.map((cell) => (
        <CandidateCard key={cell.mechanism_class} cell={cell} />
      ))}
    </div>
  );
}
