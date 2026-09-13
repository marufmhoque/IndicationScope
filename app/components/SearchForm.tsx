"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SearchForm() {
  const router = useRouter();
  const [disease, setDisease] = useState("");
  const [mechanism, setMechanism] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!disease.trim()) return;
    const params = new URLSearchParams({ disease: disease.trim() });
    if (mechanism.trim()) params.set("mechanism", mechanism.trim());
    router.push(`/results?${params.toString()}`);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-4">
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-300">
          Disease name <span className="text-indigo-400">*</span>
        </label>
        <input
          type="text"
          required
          value={disease}
          onChange={(e) => setDisease(e.target.value)}
          placeholder="e.g. Friedreich's ataxia"
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-300">
          Mechanism / target class{" "}
          <span className="text-gray-500 font-normal">(optional)</span>
        </label>
        <input
          type="text"
          value={mechanism}
          onChange={(e) => setMechanism(e.target.value)}
          placeholder="e.g. HDAC inhibitor"
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      <button
        type="submit"
        disabled={!disease.trim()}
        className="w-full rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Generate brief
      </button>
    </form>
  );
}
