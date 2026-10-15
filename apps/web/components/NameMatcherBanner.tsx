/** ADR-016 Name Matcher Radar (G-1): flag third-party mule accounts. */

export function normalizeName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
}

/** Unique alpha tokens of length >= 3 (ignores generic words like "admin"). */
const STOP = new Set(["admin", "the", "and", "toko", "shop", "store", "official", "olshop"]);

export function significantTokens(value: string): string[] {
  return normalizeName(value)
    .split(" ")
    .filter((tok) => tok.length >= 3 && !STOP.has(tok));
}

/**
 * A mismatch is flagged when the seller-provided claim shares no significant
 * token with the bank-registered holder name.
 */
export function isNameMismatch(claimed: string, actual: string | null | undefined): boolean {
  if (!claimed.trim() || !actual?.trim()) return false;
  const claimedTokens = significantTokens(claimed);
  const actualTokens = significantTokens(actual);
  if (claimedTokens.length === 0 || actualTokens.length === 0) {
    return normalizeName(claimed) !== normalizeName(actual);
  }
  return !claimedTokens.some((t) => actualTokens.includes(t));
}

export function NameMatcherBanner({
  claimedName,
  actualName,
}: {
  claimedName: string;
  actualName: string;
}) {
  return (
    <div className="rounded-2xl border-2 border-red-300 bg-red-50 p-5 shadow-xs">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-600 text-xl font-bold text-white">
          !
        </div>
        <div className="flex-1">
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-bold uppercase tracking-wide text-red-900">
              Critical alert: recipient name mismatch (money mule suspect)
            </span>
            <span className="rounded bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white">
              High danger
            </span>
          </div>
          <p className="mb-3 text-xs leading-relaxed text-red-800">
            The seller instructed you to pay to{" "}
            <b className="underline">&ldquo;{claimedName}&rdquo;</b>, but this bank account is
            legally registered to:
          </p>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-red-200 bg-white p-3">
            <div>
              <span className="block text-[11px] font-bold uppercase text-slate-500">
                Actual registered bank holder name (ADR-016 disclosed):
              </span>
              <span className="text-base font-extrabold tracking-wide text-slate-900">
                {actualName}
              </span>
            </div>
            <span className="rounded-lg border border-red-200 bg-red-100 px-2.5 py-1 text-xs font-bold text-red-800">
              Name mismatch · Do not send funds
            </span>
          </div>

          <p className="mt-2.5 text-[11px] text-red-700">
            Online fraudsters routinely rent bank accounts registered under third-party citizens.
            Never transfer money if the recipient holder name differs from the merchant you
            contacted.
          </p>
        </div>
      </div>
    </div>
  );
}
