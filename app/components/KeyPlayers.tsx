import type { Organization, Researcher } from "../lib/types";

interface Props {
  organizations: Organization[];
  researchers: Researcher[];
}

export default function KeyPlayers({ organizations, researchers }: Props) {
  // Sponsors are a mix of companies and academic centres. Separating them
  // answers two different questions — who are the competitors, and who are the
  // research groups — that a merged list answers neither of.
  // Capped per kind rather than sharing one budget: in an industry-heavy field
  // like wet AMD, a single top-N list is all companies and the research side
  // disappears entirely.
  const companies = organizations.filter((o) => o.kind === "industry").slice(0, 12);
  const institutions = organizations.filter((o) => o.kind === "academic").slice(0, 12);

  if (organizations.length === 0 && researchers.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No organizations or researchers were identified for this query.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <OrgSection
        title="Companies"
        subtitle="By trials sponsored and patents assigned"
        organizations={companies}
      />
      <OrgSection
        title="Research institutions"
        subtitle="Academic and hospital trial sponsors"
        organizations={institutions}
      />

      <section>
        <h3 className="text-sm font-semibold text-white mb-1">Leading researchers</h3>
        <p className="text-xs text-gray-500 mb-3">
          By publication count within the analyzed sample
        </p>
        {researchers.length === 0 ? (
          <p className="text-sm text-gray-600">None identified.</p>
        ) : (
          <ul className="divide-y divide-gray-800 rounded-lg border border-gray-800">
            {researchers.map((r) => (
              <li key={r.name} className="flex items-baseline gap-3 px-4 py-2.5">
                <span className="text-sm text-gray-200">{r.name}</span>
                {r.affiliation && (
                  <span className="text-xs text-gray-500 truncate">{r.affiliation}</span>
                )}
                <span className="ml-auto shrink-0 text-xs text-gray-400">
                  {r.publication_count}{" "}
                  {r.publication_count === 1 ? "paper" : "papers"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function OrgSection({
  title,
  subtitle,
  organizations,
}: {
  title: string;
  subtitle: string;
  organizations: Organization[];
}) {
  if (organizations.length === 0) return null;

  return (
    <section>
      <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
      <p className="text-xs text-gray-500 mb-3">{subtitle}</p>
      <ul className="divide-y divide-gray-800 rounded-lg border border-gray-800">
        {organizations.map((org) => (
          <li key={org.name} className="flex items-center gap-3 px-4 py-2.5">
            <span className="text-sm text-gray-200 truncate">{org.name}</span>
            <span className="ml-auto shrink-0 flex gap-2 text-xs">
              {org.trial_count > 0 && (
                <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-300">
                  {org.trial_count} {org.trial_count === 1 ? "trial" : "trials"}
                </span>
              )}
              {org.patent_count > 0 && (
                <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-300">
                  {org.patent_count} {org.patent_count === 1 ? "patent" : "patents"}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
