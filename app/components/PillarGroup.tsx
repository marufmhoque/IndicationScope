import type { MatrixCell } from "../lib/types";

interface Props {
  cells: MatrixCell[];
  render: (cell: MatrixCell) => React.ReactNode;
  emptyMessage: string;
}

/**
 * Groups mechanisms by treatment modality so the reader can see which
 * approaches a field is deploying, rather than a flat list of labels.
 *
 * Grouping is skipped when everything lands in one pillar — a single heading
 * over the whole list is noise, not structure.
 */
export default function PillarGroup({ cells, render, emptyMessage }: Props) {
  if (cells.length === 0) {
    return <p className="text-sm text-gray-500">{emptyMessage}</p>;
  }

  const groups = new Map<string, MatrixCell[]>();
  for (const cell of cells) {
    const pillar = cell.pillar || "Other";
    if (!groups.has(pillar)) groups.set(pillar, []);
    groups.get(pillar)!.push(cell);
  }

  if (groups.size <= 1) {
    return <div className="grid gap-4">{cells.map(render)}</div>;
  }

  // Largest pillars first, with Other last regardless of size — it is a
  // remainder, not a finding.
  const ordered = [...groups.entries()].sort((a, b) => {
    if (a[0] === "Other") return 1;
    if (b[0] === "Other") return -1;
    return b[1].length - a[1].length;
  });

  return (
    <div className="space-y-7">
      {ordered.map(([pillar, group]) => (
        <section key={pillar} className="break-inside-avoid">
          <div className="flex items-baseline gap-2 mb-3">
            <h3 className="text-sm font-semibold text-white print:text-black">
              {pillar}
            </h3>
            <span className="text-xs text-gray-600">
              {group.length} {group.length === 1 ? "mechanism" : "mechanisms"}
            </span>
          </div>
          <div className="grid gap-4">{group.map(render)}</div>
        </section>
      ))}
    </div>
  );
}

/** Compact modality summary for the overview area. */
export function PillarStrip({ cells }: { cells: MatrixCell[] }) {
  const counts = new Map<string, number>();
  for (const cell of cells) {
    const pillar = cell.pillar || "Other";
    counts.set(pillar, (counts.get(pillar) ?? 0) + 1);
  }
  if (counts.size === 0) return null;

  const ordered = [...counts.entries()].sort((a, b) => {
    if (a[0] === "Other") return 1;
    if (b[0] === "Other") return -1;
    return b[1] - a[1];
  });

  return (
    <div className="flex flex-wrap gap-2">
      {ordered.map(([pillar, count]) => (
        <span
          key={pillar}
          className="rounded-full border border-gray-800 bg-gray-900 px-3 py-1 text-xs text-gray-300 print:border-gray-300 print:bg-white print:text-black"
        >
          {pillar}
          <span className="ml-1.5 text-gray-500">{count}</span>
        </span>
      ))}
    </div>
  );
}
