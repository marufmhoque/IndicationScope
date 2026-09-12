"use client";

interface Props {
  open: boolean;
  /** Sections that would need generating for a complete report. */
  missing: number;
  /** Set while a full export is generating; shows progress instead of choices. */
  progress: string | null;
  onQuick: () => void;
  onFull: () => void;
  onClose: () => void;
}

/**
 * Asks before spending.
 *
 * A complete report needs a model call for every rationale and failure analysis
 * the reader never opened, so the choice — and its cost — is put in front of
 * them rather than decided silently.
 */
export default function ExportDialog({
  open,
  missing,
  progress,
  onQuick,
  onFull,
  onClose,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 print:hidden"
      onClick={progress ? undefined : onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-gray-700 bg-gray-950 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-white">Export report</h2>

        {progress ? (
          <div className="mt-5 space-y-3">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-800">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-indigo-600" />
            </div>
            <p className="text-sm text-gray-400">{progress}</p>
            <p className="text-xs text-gray-600">
              Your browser&apos;s print dialog will open when this finishes. Choose
              &ldquo;Save as PDF&rdquo; there.
            </p>
          </div>
        ) : (
          <>
            <p className="mt-2 text-sm text-gray-400">
              The report prints through your browser — choose &ldquo;Save as
              PDF&rdquo; in the dialog that opens.
            </p>

            <div className="mt-5 space-y-3">
              <button
                onClick={onFull}
                disabled={missing === 0}
                className="w-full rounded-xl border border-indigo-700 bg-indigo-950/40 p-4 text-left transition-colors hover:bg-indigo-950 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <p className="font-medium text-white">Full report</p>
                <p className="mt-0.5 text-xs text-gray-400">
                  {missing === 0
                    ? "Everything is already generated — use Quick export."
                    : `Generates ${missing} missing ${
                        missing === 1 ? "section" : "sections"
                      } first. Takes about a minute and uses your API credit.`}
                </p>
              </button>

              <button
                onClick={onQuick}
                className="w-full rounded-xl border border-gray-700 bg-gray-900 p-4 text-left transition-colors hover:bg-gray-800"
              >
                <p className="font-medium text-white">Quick export</p>
                <p className="mt-0.5 text-xs text-gray-400">
                  Prints what is already on screen. Free and immediate
                  {missing > 0
                    ? `; ${missing} ungenerated ${
                        missing === 1 ? "section is" : "sections are"
                      } marked as such.`
                    : "."}
                </p>
              </button>
            </div>

            <button
              onClick={onClose}
              className="mt-4 w-full text-sm text-gray-500 hover:text-gray-300"
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
}
