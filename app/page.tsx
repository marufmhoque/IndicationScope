"use client";

import { useState } from "react";

export default function Home() {
  const [disease, setDisease] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    // TODO: wire up to POST /api/scan
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-2xl space-y-8 text-center">
        <div>
          <h1 className="text-5xl font-bold tracking-tight text-white">
            Indication<span className="text-indigo-400">Scope</span>
          </h1>
          <p className="mt-3 text-gray-400 text-lg">
            AI-powered drug indication discovery from biomedical literature
          </p>
        </div>

        <form onSubmit={handleSearch} className="flex gap-3">
          <input
            type="text"
            value={disease}
            onChange={(e) => setDisease(e.target.value)}
            placeholder="Enter disease name (e.g. glioblastoma)"
            className="flex-1 rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <button
            type="submit"
            disabled={!disease.trim()}
            className="rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Scan
          </button>
        </form>
      </div>
    </main>
  );
}
