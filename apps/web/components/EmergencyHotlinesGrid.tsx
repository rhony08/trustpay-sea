import type { Hotline } from "@/lib/api";

interface Row {
  name: string;
  sub: string;
  dial: string;
  action: string;
}

/** Official national anti-scam command hotlines (Doc 12 §4B.4 / §4B.5). */
export const HOTLINES: Record<string, Row[]> = {
  ID: [
    { name: "OJK Anti-Scam Center (IASC)", sub: "Inter-bank rapid freeze coordination center", dial: "157", action: "tel:157" },
    { name: "Patroli Siber Polri", sub: "Official online police cybercrime portal", dial: "patrolisiber.id", action: "https://patrolisiber.id" },
    { name: "CekRekening.id", sub: "Ministry Kominfo national scam blacklist", dial: "cekrekening.id", action: "https://cekrekening.id" },
  ],
  MY: [
    { name: "National Scam Response Centre (NSRC)", sub: "Call within 24 hours to intercept stolen fund transfers", dial: "997", action: "tel:997" },
    { name: "PDRM Semak Mule", sub: "Royal Malaysia Police commercial crime mule database", dial: "semakmule.rmp.gov.my", action: "https://semakmule.rmp.gov.my" },
    { name: "BNMTELELINK", sub: "Bank Negara Malaysia consumer financial protection center", dial: "1300885465", action: "tel:1300885465" },
  ],
  SG: [
    { name: "SPF Anti-Scam Command Hotline", sub: "Singapore Police Force dedicated anti-scam unit", dial: "1799", action: "tel:1799" },
    { name: "National Crime Prevention Helpline", sub: "24-hour scam advisory and emergency guidance", dial: "18007226688", action: "tel:18007226688" },
  ],
  TH: [
    { name: "Anti Online Scam Operation Center (AOC)", sub: "Thailand national emergency anti-scam response unit", dial: "1441", action: "tel:1441" },
    { name: "Cyber Crime Investigation Bureau (CCIB)", sub: "Royal Thai Police cyber incident center", dial: "thaipoliceonline.com", action: "https://thaipoliceonline.com" },
  ],
  VN: [
    { name: "National Cyber Security Center (NCSC)", sub: "Ministry of Information & Communications cyber safety hub", dial: "khonggianmang.vn", action: "https://khonggianmang.vn" },
    { name: "Ministry of Public Security Cyber Hotline", sub: "Department of Cybersecurity & High-Tech Crime Prevention", dial: "0692348560", action: "tel:0692348560" },
  ],
  PH: [
    { name: "PNP Anti-Cybercrime Group (ACG)", sub: "Philippine National Police 24/7 scam response", dial: "09617291299", action: "tel:09617291299" },
    { name: "CIBAC / CICC Hotline", sub: "Cybercrime Investigation and Coordinating Center", dial: "1326", action: "tel:1326" },
  ],
};

function fromApi(hotlines: Hotline[]): Row[] {
  return hotlines.map((h) => ({
    name: h.name,
    sub: "Official national anti-scam resource",
    dial: h.number ?? h.url ?? "",
    action: h.number ? `tel:${h.number}` : (h.url ?? "#"),
  }));
}

export function EmergencyHotlinesGrid({
  country,
  apiHotlines,
}: {
  country: string;
  apiHotlines?: Hotline[];
}) {
  const rows = HOTLINES[country] ?? (apiHotlines?.length ? fromApi(apiHotlines) : HOTLINES.ID);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {rows.map((item, idx) => {
        const isTel = item.action.startsWith("tel");
        return (
          <div key={item.name} className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900">{item.name}</span>
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                  idx === 0 ? "bg-rose-100 text-rose-800" : "bg-slate-100 text-slate-600"
                }`}
              >
                {idx === 0 ? "Primary priority" : "Official"}
              </span>
            </div>
            <p className="mb-3 text-[11px] text-slate-500">{item.sub}</p>
            <a
              href={item.action}
              {...(isTel ? {} : { target: "_blank", rel: "noreferrer" })}
              className={`block w-full rounded-lg py-2 text-center text-xs font-bold shadow-xs transition-colors ${
                idx === 0
                  ? "bg-rose-600 text-white hover:bg-rose-700"
                  : "border border-slate-200 bg-slate-100 text-slate-800 hover:bg-slate-200"
              }`}
            >
              {isTel ? `📞 Call hotline ${item.dial}` : `Visit portal ${item.dial} →`}
            </a>
          </div>
        );
      })}
    </div>
  );
}
