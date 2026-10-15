import Link from "next/link";
import { ShieldMark } from "./Brand";

const SERVICES = [
  { href: "/check", label: "Check Account / QR" },
  { href: "/report", label: "Report a Scam" },
  { href: "/claim", label: "Merchant Dispute (Safe-Harbor)" },
  { href: "/recovery", label: "Bank Freeze Procedures" },
  { href: "/receipt", label: "Diligence Slip Generator" },
];

export function Footer() {
  return (
    <footer className="no-print border-t border-slate-200 bg-slate-100 py-12 text-xs text-slate-600">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-8 grid grid-cols-2 gap-8 md:grid-cols-4">
          <div>
            <span className="mb-3 flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 text-white">
                <ShieldMark className="h-4 w-4" />
              </span>
              <span className="text-sm font-bold text-slate-900">TrustPay SEA</span>
            </span>
            <p className="leading-relaxed text-slate-500">
              The Truecaller and Google Reviews for Southeast Asian digital payments.
            </p>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">
              Services
            </h4>
            <ul className="space-y-1.5 text-slate-600">
              {SERVICES.map((s) => (
                <li key={s.href}>
                  <Link href={s.href} className="hover:text-blue-600">
                    {s.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">
              Emergency Hotlines
            </h4>
            <ul className="space-y-1 text-[11px] text-slate-600">
              <li>
                🇮🇩 <b>Indonesia:</b> OJK 157 / IASC · Patroli Siber
              </li>
              <li>
                🇲🇾 <b>Malaysia:</b> NSRC 997 · Semak Mule
              </li>
              <li>
                🇸🇬 <b>Singapore:</b> SPF 1799
              </li>
              <li>
                🇹🇭 <b>Thailand:</b> AOC 1441
              </li>
            </ul>
          </div>

          <div>
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">
              Legal Compliance
            </h4>
            <p className="text-[11px] leading-relaxed text-slate-500">
              Strictly compliant with regional Data Privacy Acts (UU PDP, Singapore PDPA, Malaysia
              PDPA). KMS-keyed HMAC account indexing protects PII.
            </p>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between gap-2 border-t border-slate-200 pt-6 text-[11px] text-slate-500 sm:flex-row">
          <p>
            <b>Statutory Notice:</b> TrustPay SEA is an independent, community-driven payment risk
            intelligence registry. Not a bank, not a payment gateway, and does not hold consumer
            deposits.
          </p>
          <span className="shrink-0">&copy; 2026 TrustPay SEA. Open Standard.</span>
        </div>
      </div>
    </footer>
  );
}
