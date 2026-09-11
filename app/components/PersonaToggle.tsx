"use client";

import { PERSONAS } from "../lib/types";

interface Props {
  value: string;
  onChange: (persona: string) => void;
}

export default function PersonaToggle({ value, onChange }: Props) {
  const active = PERSONAS.find((p) => p.value === value) ?? PERSONAS[0];

  return (
    <div className="text-right">
      <div className="flex gap-2 justify-end">
        {PERSONAS.map((p) => (
          <button
            key={p.value}
            onClick={() => onChange(p.value)}
            title={p.blurb}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              value === p.value
                ? "bg-indigo-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {/* The distinction that matters: switching this re-interprets the same
          evidence rather than running a different search. */}
      <p className="mt-2 text-xs text-gray-500 max-w-xs ml-auto">
        Changes how results are interpreted, not what is searched.{" "}
        <span className="text-gray-600">{active.blurb}</span>
      </p>
    </div>
  );
}
