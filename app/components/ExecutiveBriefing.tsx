import { BRIEFING_SECTIONS, type ExecutiveBriefing } from "../lib/types";

interface Props {
  briefing: ExecutiveBriefing | null;
  status: "loading" | "done" | "error";
  disease: string;
}

/**
 * The opening read on a disease. Sections are independent so a partial response
 * renders what it has rather than collapsing to nothing — and a section the
 * evidence couldn't support is left out rather than filled with something
 * plausible.
 */
export default function ExecutiveBriefing({ briefing, status, disease }: Props) {
  const sections = BRIEFING_SECTIONS.filter(({ key }) => briefing?.[key]);

  return (
    <section className="rounded-2xl border border-indigo-900/70 bg-gradient-to-b from-gray-900 to-gray-900/40 p-6 print:border-gray-300 print:bg-white">
      <div className="flex items-baseline justify-between gap-4 mb-4">
        <h2 className="text-lg font-semibold text-white print:text-black">
          Executive landscape briefing
        </h2>
        <span className="text-xs text-gray-500 shrink-0">{disease}</span>
      </div>

      {status === "loading" && <BriefingSkeleton />}

      {status === "error" && (
        <p className="text-sm text-gray-500">
          The briefing could not be generated. Everything below is unaffected.
        </p>
      )}

      {status === "done" && sections.length === 0 && (
        <p className="text-sm text-gray-500">
          The sampled evidence wasn&apos;t sufficient to summarise this landscape.
        </p>
      )}

      {status === "done" && sections.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2">
          {sections.map(({ key, label }) => (
            <div key={key}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-1.5 print:text-black">
                {label}
              </h3>
              <p className="text-sm leading-relaxed text-gray-300 print:text-black">
                {briefing?.[key]}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function BriefingSkeleton() {
  return (
    <div className="grid gap-5 sm:grid-cols-2" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-3 w-28 rounded bg-gray-800 animate-pulse" />
          <div className="h-2.5 w-full rounded bg-gray-800/70 animate-pulse" />
          <div className="h-2.5 w-11/12 rounded bg-gray-800/70 animate-pulse" />
          <div className="h-2.5 w-4/5 rounded bg-gray-800/70 animate-pulse" />
        </div>
      ))}
    </div>
  );
}
