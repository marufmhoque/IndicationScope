import CandidateCard from "./CandidateCard";
import PillarGroup from "./PillarGroup";
import type { MatrixCell } from "../lib/types";

interface Props {
  candidates: MatrixCell[];
}

export default function ResultsMatrix({ candidates }: Props) {
  return (
    <PillarGroup
      cells={candidates}
      emptyMessage="No white-space candidates were identified in the ingested sample. Mechanisms with prior failures are listed under Previously Attempted."
      render={(cell) => <CandidateCard key={cell.mechanism_class} cell={cell} />}
    />
  );
}
