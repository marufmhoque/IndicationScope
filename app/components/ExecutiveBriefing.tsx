import { BRIEFING_SECTIONS, type ExecutiveBriefing } from "../lib/types";

interface Props {
  briefing: ExecutiveBriefing | null;
  status: "loading" | "done" | "error";
  disease: string;
}

const FACET_LABELS: Record<string, string> = {
  overview: "overview",
  epidemiology: "epidemiology",
  cost: "cost of illness",
};

/**
 * The disease brief. Sections are independent, so a partial response renders
 * what it has; a section the sources could not support is omitted rather than
 * filled with something plausible.
 */
export default function ExecutiveBriefing({ briefing, status, disease }: Props) {
  const sections = BRIEFING_SECTIONS.filter(({ key }) => briefing?.[key]);
  const references = briefing?.references ?? [];

  return (
    <section className="rounded-2xl border border-gray-800 bg-gray-900/60 p-6 print:border-gray-300 print:bg-white">
      <div className="mb-5 flex items-baseline justify-between gap-4 border-b border-gray-800 pb-3">
        <h2 className="text-lg font-semibold text-white print:text-black">
          Disease intelligence brief
        </h2>
        <span className="shrink-0 text-xs text-gray-500">{disease}</span>
      </div>

      {status === "loading" && <BriefingSkeleton />}

      {status === "error" && (
        <p className="text-sm text-gray-500">
          The brief could not be generated. The data below is unaffected.
        </p>
      )}

      {status === "done" && sections.length === 0 && (
        <p className="text-sm text-gray-500">
          The retrieved sources were not sufficient to write this brief.
        </p>
      )}

      {status === "done" && sections.length > 0 && (
        <div className="space-y-5">
          {sections.map(({ key, label }, i) => (
            <div key={key} className="break-inside-avoid">
              <h3 className="mb-1.5 text-sm font-semibold text-gray-200 print:text-black">
                {i + 1}. {label}
              </h3>
              <p className="text-sm leading-relaxed text-gray-300 print:text-black">
                {briefing?.[key]}
              </p>
            </div>
          ))}

          {references.length > 0 && (
            <div className="border-t border-gray-800 pt-3">
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                Background literature retrieved
              </p>
              <ul className="space-y-0.5 text-xs text-gray-500">
                {references.map((ref) => (
                  <li key={ref.pmid}>
                    <a
                      href={`https://pubmed.ncbi.nlm.nih.gov/${ref.pmid}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-400 hover:text-gray-200"
                    >
                      PMID {ref.pmid}
                    </a>{" "}
                    <span className="text-gray-600">({FACET_LABELS[ref.facet] ?? ref.facet})</span>{" "}
                    {ref.title}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function BriefingSkeleton() {
  return (
    <div className="space-y-5" aria-hidden>
      {BRIEFING_SECTIONS.map(({ key }) => (
        <div key={key} className="space-y-2">
          <div className="h-3 w-56 animate-pulse rounded bg-gray-800" />
          <div className="h-2.5 w-full animate-pulse rounded bg-gray-800/70" />
          <div className="h-2.5 w-11/12 animate-pulse rounded bg-gray-800/70" />
        </div>
      ))}
    </div>
  );
}
