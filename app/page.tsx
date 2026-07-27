import SearchForm from "./components/SearchForm";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-xl space-y-8">
        <div className="text-center">
          <h1 className="text-5xl font-bold tracking-tight text-white">
            Indication<span className="text-indigo-400">Scope</span>
          </h1>
          <p className="mt-3 text-gray-400 text-lg">
            AI-powered orphan drug indication white-space discovery
          </p>
        </div>
        <SearchForm />
      </div>
    </main>
  );
}
