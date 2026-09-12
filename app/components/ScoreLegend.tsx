"use client";

import { useState } from "react";
import type { ScoreComponents } from "../lib/types";

interface Props {
  score: number;
  components?: ScoreComponents;
}

/**
 * The score with its own explanation attached.
 *
 * A bare number invites the reader to assume a precision it doesn't have, so the
 * popover shows the actual inputs: how much literature backs the mechanism, how
 * contested its trial landscape is, and what it was measured against.
 */
export default function ScoreLegend({ score, components }: Props) {
  const [open, setOpen] = useState(false);
  const percent = Math.round(score * 100);

  return (
    <div className="relative shrink-0 text-right">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="group print:pointer-events-none"
        title="How this score is calculated"
      >
        <p className="text-xs text-gray-500 uppercase tracking-wider group-hover:text-gray-400">
          Score <span className="text-gray-600">ⓘ</span>
        </p>
        <p className="text-2xl font-bold text-indigo-400 print:text-black">{percent}</p>
      </button>

      {open && components && (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-gray-700 bg-gray-950 p-4 text-left shadow-xl print:hidden">
          <p className="text-xs text-gray-300 leading-relaxed mb-3">
            White space needs <strong className="text-white">both</strong> literature
            support and an uncontested clinic. Evidence sets the level; how open the
            trial landscape is adjusts it.
          </p>

          <dl className="space-y-1.5 text-xs">
            <Row
              label="Literature support"
              value={`${components.literature_support} of ${components.max_support} abstracts`}
              note="matching this mechanism, against the best-supported one here"
            />
            <Row
              label="Evidence"
              value={components.evidence.toFixed(2)}
              note="log-scaled, so a dominant incumbent doesn't flatten the rest"
            />
            <Row
              label="Openness"
              value={components.openness.toFixed(2)}
              note={`${components.active_trials} active of ${components.total_trials} trials`}
            />
            {components.failure_penalty > 0 && (
              <Row label="Prior failure" value="−0.40" note="a recorded failure" />
            )}
          </dl>

          <p className="mt-3 border-t border-gray-800 pt-2 text-[11px] text-gray-500">
            Scores compare mechanisms <strong>within this search</strong>, not between
            diseases — the scale is set by this disease&apos;s own literature.
          </p>
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div>
      <div className="flex justify-between gap-3">
        <dt className="text-gray-400">{label}</dt>
        <dd className="text-gray-200 tabular-nums">{value}</dd>
      </div>
      <p className="text-[11px] text-gray-600">{note}</p>
    </div>
  );
}
