"use client";

const PERSONAS = [
  { value: "academic", label: "Academic" },
  { value: "startup", label: "Startup" },
  { value: "diligence", label: "Due Diligence" },
] as const;

interface Props {
  value: string;
  onChange: (persona: string) => void;
}

export default function PersonaToggle({ value, onChange }: Props) {
  return (
    <div className="flex gap-2">
      {PERSONAS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
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
  );
}
