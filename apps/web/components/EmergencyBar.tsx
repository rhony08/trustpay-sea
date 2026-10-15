import Link from "next/link";

/** Emergency scam hotline ribbon shown above the header (Doc 12 §4B.4). */
export function EmergencyBar() {
  return (
    <div className="no-print border-b border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-900">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white">
            !
          </span>
          <span className="font-bold">Emergency Payment Scam Hotlines:</span>
          <span className="text-rose-800">
            <b>Indonesia:</b> OJK 157 / IASC · <b>Malaysia:</b> NSRC 997 · <b>Singapore:</b> 1799 ·{" "}
            <b>Thailand:</b> AOC 1441
          </span>
        </div>
        <Link
          href="/recovery"
          className="inline-flex items-center gap-1 font-bold text-rose-700 underline hover:text-rose-900"
        >
          Bank Account Freeze Guide &rarr;
        </Link>
      </div>
    </div>
  );
}
