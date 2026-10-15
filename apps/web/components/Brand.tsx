import Link from "next/link";

/** Unified Shield logo used across every prototype page (Doc 12 §4). */
export function ShieldMark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2.2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}

export function ShieldBadge({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <span
      className={`${className} flex items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs`}
    >
      <ShieldMark className="h-6 w-6" />
    </span>
  );
}

export function Brand({
  subtitle = "Digital Payment Risk & Reputation Registry",
  compact = false,
}: {
  subtitle?: string;
  compact?: boolean;
}) {
  return (
    <Link href="/" className="flex items-center gap-3 group">
      <ShieldBadge className="h-10 w-10 transition-transform group-hover:scale-105" />
      <span>
        <span className="flex items-center gap-1.5">
          <span className="text-xl font-bold tracking-tight text-slate-900">TrustPay</span>
          <span className="rounded border border-blue-200 bg-blue-100 px-1.5 py-0.5 text-[11px] font-bold text-blue-800">
            SEA
          </span>
        </span>
        {!compact && <span className="block text-[11px] font-medium text-slate-500">{subtitle}</span>}
      </span>
    </Link>
  );
}
