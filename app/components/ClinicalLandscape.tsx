import MechanismCard from "./MechanismCard";
import PillarGroup from "./PillarGroup";
import type { MatrixCell } from "../lib/types";

interface Props {
  cells: MatrixCell[];
}

/** Mechanism classes found in the examined trials and literature, grouped by modality. */
export default function ClinicalLandscape({ cells }: Props) {
  return (
    <PillarGroup
      cells={cells}
      emptyMessage="No mechanism classes were identified in the examined trials and literature."
      render={(cell) => <MechanismCard key={cell.mechanism_class} cell={cell} />}
    />
  );
}
