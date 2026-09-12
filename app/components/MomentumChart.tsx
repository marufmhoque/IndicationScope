import {
  PHASE_LABELS,
  PHASE_ORDER,
  type PhaseDistribution,
  type PublicationTrend,
} from "../lib/types";

interface Props {
  trend: PublicationTrend;
  phases: PhaseDistribution;
}

// Hand-rolled SVG rather than a charting library: two small charts don't justify
// a dependency, and inline SVG prints correctly without a canvas rasterisation step.
const BAR_W = 34;
const BAR_GAP = 10;
const CHART_H = 92;

export default function MomentumChart({ trend, phases }: Props) {
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <PublicationTrendChart trend={trend} />
      <PhaseChart phases={phases} />
    </div>
  );
}

function PublicationTrendChart({ trend }: { trend: PublicationTrend }) {
  const years = Object.keys(trend.years)
    .map(Number)
    .sort((a, b) => a - b);

  if (years.length === 0) {
    return (
      <Panel title="Publication volume">
        <p className="text-xs text-gray-500">
          Trend unavailable for this query.
        </p>
      </Panel>
    );
  }

  const max = Math.max(...years.map((y) => trend.years[String(y)] ?? 0), 1);
  const width = years.length * (BAR_W + BAR_GAP);

  return (
    <Panel title="Publication volume" subtitle={describeTrend(trend)}>
      <svg
        viewBox={`0 0 ${width} ${CHART_H + 20}`}
        className="w-full h-auto max-h-36"
        role="img"
        aria-label="Publications per year"
      >
        {years.map((year, i) => {
          const count = trend.years[String(year)] ?? 0;
          const h = Math.max((count / max) * CHART_H, 2);
          const x = i * (BAR_W + BAR_GAP);
          // The current year is always mid-flight. Drawn hollow so a partial
          // count can't be read as a collapse in output.
          const partial = year === trend.partial_year;
          return (
            <g key={year}>
              <rect
                x={x}
                y={CHART_H - h}
                width={BAR_W}
                height={h}
                rx={2}
                className={partial ? "fill-gray-700" : "fill-indigo-500"}
                strokeDasharray={partial ? "3 2" : undefined}
                stroke={partial ? "currentColor" : undefined}
                strokeWidth={partial ? 1 : 0}
              />
              <text
                x={x + BAR_W / 2}
                y={CHART_H - h - 3}
                textAnchor="middle"
                className="fill-gray-400 text-[9px]"
              >
                {count.toLocaleString()}
              </text>
              <text
                x={x + BAR_W / 2}
                y={CHART_H + 13}
                textAnchor="middle"
                className="fill-gray-500 text-[9px]"
              >
                {year}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="text-[11px] text-gray-600 mt-1">
        {trend.partial_year} is still in progress and is shown outlined — its bar is
        not comparable to complete years.
      </p>
    </Panel>
  );
}

function PhaseChart({ phases }: { phases: PhaseDistribution }) {
  const counts = phases.counts ?? {};
  const entries = PHASE_ORDER.filter((p) => counts[p]).map((p) => ({
    key: p,
    label: PHASE_LABELS[p] ?? p,
    count: counts[p],
  }));
  // Bar widths are shares of all phase assignments, which exceed the trial
  // count when a trial is registered across two phases.
  const total = entries.reduce((sum, e) => sum + e.count, 0);

  if (total === 0) {
    return (
      <Panel title="Trial phases">
        <p className="text-xs text-gray-500">No phase data for this query.</p>
      </Panel>
    );
  }


  return (
    <Panel
      title="Trial phases"
      subtitle={`${phases.phased_trials} of ${phases.total_trials} ingested trials carry a phase`}
    >
      <div className="flex h-5 w-full overflow-hidden rounded">
        {entries.map((e) => (
          <div
            key={e.key}
            className={phaseColor(e.key)}
            style={{ width: `${(e.count / total) * 100}%` }}
            title={`${e.label}: ${e.count}`}
          />
        ))}
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5">
        {entries.map((e) => (
          <li key={e.key} className="flex items-center gap-1.5 text-[11px]">
            <span className={`h-2 w-2 rounded-sm ${phaseColor(e.key)}`} />
            <span className="text-gray-400">{e.label}</span>
            <span className="ml-auto text-gray-500">{e.count}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/**
 * Describe the trend from complete years only. A flat field is a real finding —
 * publication volume for wet AMD and progeria is both flat — so this must never
 * default to implying growth.
 */
function describeTrend(trend: PublicationTrend): string {
  const complete = Object.keys(trend.years)
    .map(Number)
    .filter((y) => y !== trend.partial_year)
    .sort((a, b) => a - b);

  if (complete.length < 2) return "Not enough complete years to judge direction";

  const first = trend.years[String(complete[0])] ?? 0;
  const last = trend.years[String(complete[complete.length - 1])] ?? 0;
  if (first === 0) return "Direction unclear";

  const change = (last - first) / first;
  if (change > 0.15) return `Growing — up ${Math.round(change * 100)}% since ${complete[0]}`;
  if (change < -0.15) return `Declining — down ${Math.round(-change * 100)}% since ${complete[0]}`;
  return `Steady — broadly flat since ${complete[0]}`;
}

function phaseColor(phase: string): string {
  switch (phase) {
    case "EARLY_PHASE1":
    case "PHASE1":
      return "bg-sky-700";
    case "PHASE2":
      return "bg-indigo-600";
    case "PHASE3":
      return "bg-violet-600";
    case "PHASE4":
      return "bg-emerald-600";
    default:
      // Observational and non-applicable studies. Their own band, never
      // dropped — they are a third of the record for some diseases.
      return "bg-gray-700";
  }
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 print:border-gray-300 print:bg-white">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 print:text-black">
        {title}
      </h3>
      {subtitle && <p className="text-[11px] text-gray-500 mb-2">{subtitle}</p>}
      {children}
    </div>
  );
}
