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
 * The printable briefing.
 *
 * Hidden on screen and shown only in print. The screen view is tabbed, so only
 * one section is mounted at a time — a report has to contain all of them at
 * once, which is why this exists rather than restyling the live page.
 */
export default function ReportDocument({
  scan,
  briefing,
  rationales,
  failures,
}: Props) {
  return (
    <div className="hidden print:block text-black">
      <header className="mb-6 border-b border-gray-400 pb-3">
        <h1 className="text-2xl font-bold">{scan.query.disease}</h1>
        <p className="text-xs text-gray-700">
          Disease intelligence briefing · generated{" "}
          {new Date(scan.generated_at).toLocaleString()} · IndicationScope
        </p>
      </header>

      <Section title="Coverage">
        <p className="text-sm">{scan.coverage_note}</p>
        <ul className="mt-1 text-xs text-gray-700">
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
            {scan.coverage.trials_classified} of {scan.coverage.trials_total} ingested
            trials.
          </li>
        </ul>
      </Section>

      {briefing && BRIEFING_SECTIONS.some(({ key }) => briefing[key]) && (
        <Section title="Executive summary">
          {BRIEFING_SECTIONS.filter(({ key }) => briefing[key]).map(
            ({ key, label }) => (
              <div key={key} className="mb-3 break-inside-avoid">
                <h3 className="text-sm font-semibold">{label}</h3>
                <p className="text-sm leading-relaxed">{briefing[key]}</p>
              </div>
            )
          )}
        </Section>
      )}

      <Section title="Research momentum">
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

      <Section title="Standard of care & active landscape">
        {scan.standard_of_care.length === 0 ? (
          <p className="text-sm">
            No mechanism in the ingested sample carries enough trial activity to
            characterise a standard of care.
          </p>
        ) : (
          scan.standard_of_care.slice(0, 10).map((cell) => (
            <MechanismLine key={cell.mechanism_class} cell={cell} />
          ))
        )}
      </Section>

      <Section title="White space opportunities">
        {scan.candidates.length === 0 ? (
          <p className="text-sm">
            No white-space candidates were identified in the ingested sample.
          </p>
        ) : (
          scan.candidates.slice(0, 10).map((cell) => (
            <div key={cell.mechanism_class} className="mb-3 break-inside-avoid">
              <MechanismLine cell={cell} showScore />
              <p className="text-sm leading-relaxed">
                {rationales[cell.mechanism_class] ?? (
                  <span className="italic text-gray-600">
                    Rationale not generated for this export.
                  </span>
                )}
              </p>
            </div>
          ))
        )}
      </Section>

      <Section title="Previously attempted & why they failed">
        {scan.previously_attempted.length === 0 ? (
          <p className="text-sm">
            No mechanism in the ingested sample carries a prior-failure signal.
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
                        <span className="font-medium uppercase text-[10px] mr-1">
                          {point.category}
                        </span>
                        {point.reason}
                        {point.citations.length > 0 && (
                          <span className="text-gray-600">
                            {" "}
                            ({point.citations.join(", ")})
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {analysis && analysis.failure_points.length === 0 && !analysis.summary && (
                  <p className="text-sm italic text-gray-600">
                    The trial record doesn&apos;t state why these attempts stopped.
                  </p>
                )}
                {!analysis && (
                  <p className="text-sm italic text-gray-600">
                    Failure analysis not generated for this export.
                  </p>
                )}
              </div>
            );
          })
        )}
      </Section>

      <Section title="Key players">
        <p className="text-sm">
          <strong>Organisations:</strong>{" "}
          {scan.key_organizations
            .slice(0, 12)
            .map((o) => `${o.name} (${o.trial_count})`)
            .join(" · ") || "none identified"}
        </p>
        <p className="mt-1 text-sm">
          <strong>Researchers:</strong>{" "}
          {scan.key_researchers
            .slice(0, 12)
            .map((r) => `${r.name} (${r.publication_count})`)
            .join(" · ") || "none identified"}
        </p>
      </Section>

      <footer className="mt-6 border-t border-gray-400 pt-3 text-[10px] leading-relaxed text-gray-700">
        <p>
          <strong>Method and limits.</strong> Built from ClinicalTrials.gov, PubMed,
          Google Patents and the USPTO Open Data Portal. Mechanism classes and all
          narrative sections are model-generated from the sampled sources above and
          are not a literature review. Scores rank mechanisms within this search
          only and are not comparable across diseases. Trial activity is not
          regulatory approval — this data contains no approval status, and Phase 4
          indicates post-marketing study. Verify every cited PMID and NCT ID before
          relying on it.
        </p>
      </footer>
    </div>
  );
}

function MechanismLine({
  cell,
  showScore = false,
}: {
  cell: MatrixCell;
  showScore?: boolean;
}) {
  const total = Object.values(cell.trial_count_by_status ?? {}).reduce(
    (a, b) => a + b,
    0
  );
  return (
    <p className="text-sm font-semibold">
      {cell.mechanism_class}
      {showScore && (
        <span className="ml-2 font-normal">
          score {Math.round(cell.white_space_score * 100)}
        </span>
      )}
      <span className="ml-2 font-normal text-gray-700">
        {total} {total === 1 ? "trial" : "trials"} · {cell.literature_support}{" "}
        abstracts
        {cell.pillar ? ` · ${cell.pillar}` : ""}
      </span>
    </p>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5 break-inside-avoid">
      <h2 className="mb-1.5 border-b border-gray-300 pb-1 text-base font-bold">
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
