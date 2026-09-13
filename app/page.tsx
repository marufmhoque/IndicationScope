import SearchForm from "./components/SearchForm";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-xl space-y-8">
        <div className="text-center">
          <h1 className="text-5xl font-bold tracking-tight text-white">
            Indication<span className="text-indigo-400">Scope</span>
          </h1>
          <p className="mt-4 text-base leading-relaxed text-gray-400">
            Enter a disease to generate a structured intelligence brief. IndicationScope
            retrieves registered clinical trials, published literature and patents, and
            summarises the disease&apos;s biology, epidemiology, current treatment, active
            research and past trial failures, with each statement linked to its source.
          </p>
        </div>
        <SearchForm />
      </div>
    </main>
  );
}
