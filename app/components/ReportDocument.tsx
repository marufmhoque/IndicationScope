import {
  BRIEFING_SECTIONS,
  PHASE_LABELS,
  PHASE_ORDER,
  type ExecutiveBriefing,
  type FailureAnalysis,
  type MatrixCell,
  type ScanResponse,
} from "../lib/types";

interface Props {
  scan: ScanResponse;
  briefing: ExecutiveBriefing | null;
  rationales: Record<string, string>;
  failures: Record<string, FailureAnalysis>;
}

/**
 * The printable brief.
 *
 * Hidden on screen and shown only in print. The screen view is tabbed, so only one
 * section is mounted at a time — a report has to contain all of them at once.
 */
export default function ReportDocument({ scan, briefing, rationales, failures }: Props) {
  const references = briefing?.references ?? [];

  return (
    <div className="hidden print:block text-black">
      <header className="mb-6 border-b border-gray-400 pb-3">
        <h1 className="text-2xl font-bold">{scan.query.disease}</h1>
        <p className="text-xs text-gray-700">
          Disease intelligence brief · generated{" "}
          {new Date(scan.generated_at).toLocaleString()} · IndicationScope
        </p>
      </header>

      <Section title="Data examined">
        {/* Not coverage_note: that sentence is written as an instruction to the model. */}
        <ul className="text-xs text-gray-700">
          <li>
            Trials: {scan.sampling.trials.ingested.toLocaleString()} of{" "}
            {scan.sampling.trials.total.toLocaleString()} registered (
            {formatPercent(scan.sampling.trials.fraction)})
          </li>
          <li>
            Publications: {scan.sampling.publications.ingested.toLocaleString()} of{" "}
            {scan.sampling.publications.total.toLocaleString()} (
            {formatPercent(scan.sampling.publications.fraction)})
          </li>
          <li>
            Patents: {scan.patents_analyzed.toLocaleString()} of{" "}
            {scan.patent_count.toLocaleString()}
          </li>
          <li>
            Mechanism classification reached {scan.coverage.drugs_classified} of{" "}
            {scan.coverage.distinct_drugs} distinct interventions, covering{" "}
            {scan.coverage.trials_classified} of {scan.coverage.trials_total} examined
            trials.
          </li>
        </ul>
      </Section>

      {briefing && BRIEFING_SECTIONS.some(({ key }) => briefing[key]) ? (
        BRIEFING_SECTIONS.filter(({ key }) => briefing[key]).map(({ key, label }, i) => (
          <Section key={key} title={`${i + 1}. ${label}`}>
            <p className="text-sm leading-relaxed">{briefing[key]}</p>
          </Section>
        ))
      ) : (
        <Section title="Disease intelligence brief">
          <p className="text-sm italic text-gray-600">Brief not generated for this export.</p>
        </Section>
      )}

      <Section title="Publication volume and trial phases">
        <p className="text-sm">
          Publications per year:{" "}
          {Object.keys(scan.publication_trend.years).length === 0
            ? "unavailable"
            : Object.entries(scan.publication_trend.years)
                .sort()
                .map(
                  ([year, count]) =>
                    `${year}: ${count.toLocaleString()}${
                      Number(year) === scan.publication_trend.partial_year
                        ? " (incomplete)"
                        : ""
                    }`
                )
                .join(" · ")}
        </p>
        <p className="mt-1 text-sm">
          Trial phases:{" "}
          {PHASE_ORDER.filter((p) => scan.phase_distribution.counts?.[p])
            .map((p) => `${PHASE_LABELS[p] ?? p}: ${scan.phase_distribution.counts[p]}`)
            .join(" · ") || "no phase data"}
        </p>
      </Section>

      <Section title="Mechanism classes in the examined record">
        {scan.mechanisms.length === 0 ? (
          <p className="text-sm">No mechanism classes were identified.</p>
        ) : (
          scan.mechanisms.slice(0, 15).map((cell) => (
            <div key={cell.mechanism_class} className="mb-3 break-inside-avoid">
              <MechanismLine cell={cell} />
              {rationales[cell.mechanism_class] && (
                <p className="text-sm leading-relaxed">{rationales[cell.mechanism_class]}</p>
              )}
            </div>
          ))
        )}
      </Section>

      <Section title="Mechanism classes with terminated or negative trials">
        {scan.previously_attempted.length === 0 ? (
          <p className="text-sm">
            No mechanism class in the examined trials has a trial recorded as terminated or
            completed with a negative result.
          </p>
        ) : (
          scan.previously_attempted.map((cell) => {
            const analysis = failures[cell.mechanism_class];
            return (
              <div key={cell.mechanism_class} className="mb-3 break-inside-avoid">
                <MechanismLine cell={cell} />
                {analysis?.summary && (
                  <p className="text-sm leading-relaxed">{analysis.summary}</p>
                )}
                {analysis && analysis.failure_points.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-sm">
                    {analysis.failure_points.map((point, i) => (
                      <li key={i}>
                        <span className="mr-1 text-[10px] font-medium uppercase">
                          {point.category}
                        </span>
                        {point.reason}
                        {point.citations.length > 0 && (
                          <span className="text-gray-600"> ({point.citations.join(", ")})</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {analysis && analysis.failure_points.length === 0 && !analysis.summary && (
                  <p className="text-sm italic text-gray-600">
                    The trial record does not state why these trials stopped.
                  </p>
                )}
                {!analysis && (
                  <p className="text-sm italic text-gray-600">
                    Summary not generated for this export.
                  </p>
                )}
              </div>
            );
          })
        )}
      </Section>

      <Section title="Sponsors, assignees and authors">
        <p className="text-sm">
          <strong>Organisations:</strong>{" "}
          {scan.key_organizations
            .slice(0, 12)
            .map((o) => `${o.name} (${o.trial_count} trials, ${o.patent_count} patents)`)
            .join(" · ") || "none identified"}
        </p>
        <p className="mt-1 text-sm">
          <strong>Authors:</strong>{" "}
          {scan.key_researchers
            .slice(0, 12)
            .map((r) => `${r.name} (${r.publication_count})`)
            .join(" · ") || "none identified"}
        </p>
      </Section>

      {references.length > 0 && (
        <Section title="Background literature">
          <ul className="text-xs">
            {references.map((ref) => (
              <li key={ref.pmid}>
                PMID {ref.pmid} ({ref.facet}): {ref.title}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <footer className="mt-6 border-t border-gray-400 pt-3 text-[10px] leading-relaxed text-gray-700">
        <p>
          <strong>Method and limits.</strong> Compiled from ClinicalTrials.gov, PubMed,
          Google Patents and the USPTO Open Data Portal. Mechanism classes and all
          narrative sections are model-generated from the sources listed and are not a
          systematic review. Counts describe the examined records, which may be a sample
          of a larger registry or literature. Trial registration is not regulatory
          approval — the data contains no approval status, and Phase 4 indicates
          post-marketing study. Verify each cited PMID and NCT ID before relying on it.
        </p>
      </footer>
    </div>
  );
}

function MechanismLine({ cell }: { cell: MatrixCell }) {
  const counts = cell.trial_count_by_status ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <p className="text-sm font-semibold">
      {cell.mechanism_class}
      <span className="ml-2 font-normal text-gray-700">
        {cell.target ? `target ${cell.target} · ` : ""}
        {total} {total === 1 ? "trial" : "trials"} · {counts.ACTIVE ?? 0} active ·{" "}
        {cell.literature_support} abstracts
        {cell.pillar ? ` · ${cell.pillar}` : ""}
      </span>
    </p>
  );
}

/**
 * Sections may break across pages: several run longer than a page, and forbidding
 * the break pushed each one to a fresh page behind a blank gap (11 pages for ~6 of
 * content). Only the heading is kept with what follows; individual entries keep
 * their own break-inside-avoid.
 */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-5">
      <h2 className="mb-1.5 border-b border-gray-300 pb-1 text-base font-bold [break-after:avoid]">
        {title}
      </h2>
      {children}
    </section>
  );
}

function formatPercent(fraction: number): string {
  if (fraction >= 0.995) return "100%";
  if (fraction > 0 && fraction < 0.01) return "<1%";
  return `${Math.round(fraction * 100)}%`;
}
