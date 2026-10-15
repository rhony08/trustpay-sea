"use client";

import type { Hotline } from "@/lib/api";
import { useI18n } from "./LocaleProvider";

interface Row {
  name: string;
  subKey: string;
  dial: string;
  action: string;
}

/** Official national anti-scam command hotlines (Doc 12 §4B.4 / §4B.5). */
export const HOTLINES: Record<string, Row[]> = {
  ID: [
    { name: "OJK Anti-Scam Center (IASC)", subKey: "hotline.ID.1", dial: "157", action: "tel:157" },
    { name: "Patroli Siber Polri", subKey: "hotline.ID.2", dial: "patrolisiber.id", action: "https://patrolisiber.id" },
    { name: "CekRekening.id", subKey: "hotline.ID.3", dial: "cekrekening.id", action: "https://cekrekening.id" },
  ],
  MY: [
    { name: "National Scam Response Centre (NSRC)", subKey: "hotline.MY.1", dial: "997", action: "tel:997" },
    { name: "PDRM Semak Mule", subKey: "hotline.MY.2", dial: "semakmule.rmp.gov.my", action: "https://semakmule.rmp.gov.my" },
    { name: "BNMTELELINK", subKey: "hotline.MY.3", dial: "1300885465", action: "tel:1300885465" },
  ],
  SG: [
    { name: "SPF Anti-Scam Command Hotline", subKey: "hotline.SG.1", dial: "1799", action: "tel:1799" },
    { name: "National Crime Prevention Helpline", subKey: "hotline.SG.2", dial: "18007226688", action: "tel:18007226688" },
  ],
  TH: [
    { name: "Anti Online Scam Operation Center (AOC)", subKey: "hotline.TH.1", dial: "1441", action: "tel:1441" },
    { name: "Cyber Crime Investigation Bureau (CCIB)", subKey: "hotline.TH.2", dial: "thaipoliceonline.com", action: "https://thaipoliceonline.com" },
  ],
  VN: [
    { name: "National Cyber Security Center (NCSC)", subKey: "hotline.VN.1", dial: "khonggianmang.vn", action: "https://khonggianmang.vn" },
    { name: "Ministry of Public Security Cyber Hotline", subKey: "hotline.VN.2", dial: "0692348560", action: "tel:0692348560" },
  ],
  PH: [
    { name: "PNP Anti-Cybercrime Group (ACG)", subKey: "hotline.PH.1", dial: "09617291299", action: "tel:09617291299" },
    { name: "CIBAC / CICC Hotline", subKey: "hotline.PH.2", dial: "1326", action: "tel:1326" },
  ],
};

function fromApi(hotlines: Hotline[]): Row[] {
  return hotlines.map((h) => ({
    name: h.name,
    subKey: "recovery.hotlineSub",
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
  const { t } = useI18n();
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
                {idx === 0 ? t("recovery.primary") : t("recovery.official")}
              </span>
            </div>
            <p className="mb-3 text-[11px] text-slate-500">{t(item.subKey)}</p>
            <a
              href={item.action}
              {...(isTel ? {} : { target: "_blank", rel: "noreferrer" })}
              className={`block w-full rounded-lg py-2 text-center text-xs font-bold shadow-xs transition-colors ${
                idx === 0
                  ? "bg-rose-600 text-white hover:bg-rose-700"
                  : "border border-slate-200 bg-slate-100 text-slate-800 hover:bg-slate-200"
              }`}
            >
              {isTel
                ? t("recovery.callHotline", { dial: item.dial })
                : t("recovery.visitPortal", { dial: item.dial })}
            </a>
          </div>
        );
      })}
    </div>
  );
}
