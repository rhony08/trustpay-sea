"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  BANKS,
  COUNTRIES,
  FLAG_REASONS,
  REPORT_CATEGORIES,
  addWatch,
  createAnonymousReport,
  createReport,
  decodeQrImage,
  flagReport,
  getToken,
  screenAccount,
  screenQr,
  searchPhone,
  setToken,
  type PhoneSearchResult,
  type ReportView,
  type ScreenResult,
} from "@/lib/api";
import { riskBand } from "@/lib/risk";
import { isNameMismatch, NameMatcherBanner } from "@/components/NameMatcherBanner";
import { RiskGauge } from "@/components/RiskGauge";
import { CoolingOffTimer } from "@/components/CoolingOffTimer";
import { RedactedSlipViewer } from "@/components/RedactedSlipViewer";
import { ReportCard } from "@/components/ReportCard";
import { useI18n } from "@/components/LocaleProvider";

type Tab = "account" | "phone" | "qr";

const REPORTS_PER_PAGE = 10;

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

function hasFreshReports(result: ScreenResult): boolean {
  if (result.status !== "success") return false;
  const cutoff = Date.now() - 72 * 3600 * 1000;
  return (result.data.reports ?? []).some(
    (r) => r.created_at !== null && Date.parse(r.created_at) > cutoff,
  );
}

export default function CheckPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("account");
  const [country, setCountry] = useState("ID");
  const [bank, setBank] = useState("014");
  const [account, setAccount] = useState("");
  const [nameClaim, setNameClaim] = useState("");
  const [phone, setPhone] = useState("");
  const [payload, setPayload] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [phoneResult, setPhoneResult] = useState<PhoneSearchResult | null>(null);
  const [flagged, setFlagged] = useState<ReportView | null>(null);
  const [reportOpen, setReportOpen] = useState(false);

  const run = useCallback(
    async (fn: () => Promise<ScreenResult>) => {
      setBusy(true);
      setError(null);
      setResult(null);
      setPhoneResult(null);
      try {
        setResult(await fn());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("common.errorRequest"));
      } finally {
        setBusy(false);
      }
    },
    [t],
  );

  const runPhone = useCallback(async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    setPhoneResult(null);
    try {
      const next = await searchPhone(country, phone);
      setPhoneResult(next.data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("common.errorRequest"));
    } finally {
      setBusy(false);
    }
  }, [country, phone, t]);

  // Deep-link hydration: home search + shared QR both land here.
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const qr = sp.get("qr");
    if (qr) {
      setTab("qr");
      setPayload(qr);
      void run(() => screenQr(qr));
      return;
    }
    const nextTab = (sp.get("tab") as Tab | null) ?? "account";
    setTab(nextTab);
    const c = sp.get("country");
    const b = sp.get("bank");
    const a = sp.get("account");
    const claim = sp.get("nameClaim");
    const p = sp.get("phone");
    const pl = sp.get("payload");
    if (c) setCountry(c);
    if (b) setBank(b);
    if (claim) setNameClaim(claim);
    if (p) setPhone(p);
    if (pl) setPayload(pl);
    if (nextTab === "account" && a && c && b) {
      setAccount(a);
      void run(() => screenAccount({ country: c, bank: b, account: a }));
    } else if (nextTab === "phone" && p && c) {
      void searchPhone(c, p)
        .then((r) => setPhoneResult(r.data))
        .catch(() => undefined);
    } else if (nextTab === "qr" && pl) {
      void run(() => screenQr(pl));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="flex-1 py-8 sm:py-10">
      <div className="mx-auto max-w-4xl px-4 sm:px-6">
        <div className="mb-6">
          <Link href="/" className="mb-1 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-blue-600">
            {t("common.backToSearch")}
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">{t("check.title")}</h1>
        </div>

        {/* Search form */}
        <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="mb-3 flex gap-2 text-xs font-semibold">
            {(["account", "phone", "qr"] as Tab[]).map((tabKey) => (
              <button
                key={tabKey}
                onClick={() => setTab(tabKey)}
                className={`rounded-lg px-3 py-1.5 ${
                  tab === tabKey ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {tabKey === "account"
                  ? t("check.tabAccount")
                  : tabKey === "phone"
                    ? t("check.tabPhone")
                    : t("check.tabQr")}
              </button>
            ))}
          </div>

          {tab === "account" && (
            <form
              className="grid grid-cols-1 items-end gap-3 sm:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                void run(() => screenAccount({ country, bank, account }));
              }}
            >
              <div>
                <MiniLabel>{t("common.country")}</MiniLabel>
                <select
                  className={inputCls}
                  value={country}
                  onChange={(e) => {
                    setCountry(e.target.value);
                    setBank(BANKS[e.target.value]?.[0]?.code ?? bank);
                  }}
                >
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <MiniLabel>{t("check.institution")}</MiniLabel>
                <select className={inputCls} value={bank} onChange={(e) => setBank(e.target.value)}>
                  {(BANKS[country] ?? []).map((b) => (
                    <option key={b.code} value={b.code}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <MiniLabel>{t("check.accountNumber")}</MiniLabel>
                <input
                  required
                  inputMode="numeric"
                  className={`${inputCls} font-mono`}
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder="8831924831"
                />
              </div>
              <div>
                <MiniLabel>{t("check.sellerClaimed")}</MiniLabel>
                <input
                  className={`${inputCls} border-blue-200 bg-blue-50/50`}
                  value={nameClaim}
                  onChange={(e) => setNameClaim(e.target.value)}
                  placeholder={t("check.sellerClaimedPlaceholder")}
                />
              </div>
              <div className="sm:col-span-4">
                <button
                  type="submit"
                  disabled={busy || !account}
                  className="w-full rounded-lg bg-blue-600 py-2 text-sm font-bold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50"
                >
                  {busy ? t("common.checking") : t("check.reVerify")}
                </button>
              </div>
            </form>
          )}

          {tab === "phone" && (
            <form
              className="flex flex-col gap-3 sm:flex-row sm:items-end"
              onSubmit={(e) => {
                e.preventDefault();
                void runPhone();
              }}
            >
              <div className="sm:w-40">
                <MiniLabel>{t("common.country")}</MiniLabel>
                <select className={inputCls} value={country} onChange={(e) => setCountry(e.target.value)}>
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <MiniLabel>{t("check.phone")}</MiniLabel>
                <input
                  required
                  inputMode="tel"
                  className={`${inputCls} font-mono`}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="0812…"
                />
              </div>
              <button
                type="submit"
                disabled={busy || !phone}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? t("common.checking") : t("check.checkWallets")}
              </button>
            </form>
          )}

          {tab === "qr" && (
            <form
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                void run(() => screenQr(payload));
              }}
            >
              <textarea
                rows={2}
                className={`${inputCls} font-mono text-xs`}
                placeholder={t("check.pastePayload")}
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
              />
              <div className="flex flex-col gap-2 sm:flex-row">
                <label className="flex-1 cursor-pointer rounded-lg border border-dashed border-slate-300 px-4 py-2 text-center text-sm text-slate-500 hover:border-blue-500 hover:text-slate-700">
                  {t("check.uploadQr")}
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setBusy(true);
                      setError(null);
                      setResult(null);
                      try {
                        const decoded = await decodeQrImage(file);
                        setPayload(decoded);
                        setResult(await screenQr(decoded));
                      } catch (err) {
                        setError(err instanceof ApiError ? err.message : t("check.decodeFailed"));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy || !payload}
                  className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {busy ? t("common.checking") : t("check.screenQr")}
                </button>
              </div>
            </form>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </div>
        )}

        {result && (
          <ResultView
            result={result}
            nameClaim={nameClaim}
            onFlag={setFlagged}
            onReport={() => setReportOpen(true)}
            reportHref={`/report?country=${encodeURIComponent(country)}&bank=${encodeURIComponent(
              bank,
            )}&account=${encodeURIComponent(account)}`}
          />
        )}
        {phoneResult && <PhoneResultCard data={phoneResult} />}
      </div>

      {flagged && <FlagModal report={flagged} onClose={() => setFlagged(null)} />}
      {reportOpen && (
        <ReportModal
          country={country}
          bank={bank}
          account={account}
          onClose={() => setReportOpen(false)}
        />
      )}
    </main>
  );
}

function MiniLabel({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  void t;
  return <label className="mb-0.5 block text-[11px] font-bold text-slate-500">{children}</label>;
}

function ResultView({
  result,
  nameClaim,
  onFlag,
  onReport,
  reportHref,
}: {
  result: ScreenResult;
  nameClaim: string;
  onFlag: (r: ReportView) => void;
  onReport: () => void;
  reportHref: string;
}) {
  const { t } = useI18n();
  if (result.status === "not_found") {
    const meta = result.data.qr_metadata;
    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-300 bg-white p-6 shadow-xs">
          <span className="inline-block rounded-lg border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-extrabold uppercase tracking-wide text-amber-800">
            {t("check.unreviewed")}
          </span>
          <h2 className="mt-2 text-lg font-bold text-slate-900">{t("check.notInRegistry")}</h2>
          <p className="mt-1 text-sm text-slate-600">{result.data.message}</p>
          <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {t("check.unreviewedWarning")}
          </p>
          {meta && (
            <dl className="mt-3 space-y-1 text-sm text-slate-600">
              <Row k={t("check.merchant")} v={meta.merchant_name} />
              <Row k={t("check.city")} v={meta.merchant_city} />
              <Row k={t("check.scheme")} v={meta.scheme} />
              <Row k={t("check.nmid")} v={meta.national_merchant_id} />
              {meta.homoglyph_warning && (
                <p className="text-amber-600">{t("check.lookalike")}</p>
              )}
            </dl>
          )}
          <GovCheckBanner check={result.data.gov_check} />
          <button
            onClick={onReport}
            className="mt-4 w-full rounded-lg bg-rose-600 px-3.5 py-2 text-sm font-bold text-white shadow-xs hover:bg-rose-700"
          >
            {t("check.reportThis")}
          </button>
        </div>
      </div>
    );
  }

  const {
    entity,
    risk_assessment: risk,
    community_signals: community,
    qr_metadata: meta,
    ai_summary,
    related_fact_checks,
    search_intelligence,
    gov_check,
  } = result.data;
  const reports = result.data.reports ?? [];
  const band = riskBand(risk.risk_score);
  const mismatch = isNameMismatch(nameClaim, entity.holder?.name);

  return (
    <div className="space-y-6">
      {mismatch && entity.holder && (
        <NameMatcherBanner claimedName={nameClaim} actualName={entity.holder.name} />
      )}

      {(hasFreshReports(result) || risk.risk_level === "HIGH_RISK" || risk.risk_level === "CRITICAL_FRAUD") && (
        <CoolingOffTimer />
      )}

      <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-6">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {entity.institution ?? entity.scheme ?? entity.entity_type} · {entity.country}
              </span>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                {t("common.exactMatch")}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-3xl font-bold tracking-wider text-slate-900">
                {entity.account_masked}
              </span>
            </div>
            {entity.holder ? (
              <div className="mt-2.5 flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500">{t("check.accountHolder")}</span>
                <span className="text-sm font-bold text-slate-900">{entity.holder.name}</span>
                <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                  {entity.holder.label}
                </span>
              </div>
            ) : (
              <p className="mt-2 text-xs text-slate-500">
                {t("check.holderUndisclosed")}
              </p>
            )}
          </div>

          <div className="space-y-2 text-right">
            <span
              className={`inline-block rounded-lg border px-3.5 py-1.5 text-xs font-extrabold uppercase tracking-wide ${band.badge}`}
            >
              {t(`level.${risk.risk_level}`)}
            </span>
            {risk.anomaly_spike_detected && (
              <p className="text-[11px] text-amber-600">{t("check.anomaly")}</p>
            )}
            <div className="flex flex-wrap justify-end gap-2">
              <button
                onClick={onReport}
                className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-rose-700"
              >
                {t("check.reportThis")}
              </button>
              <WatchButton entityId={entity.id} />
              <Link
                href={`/claim?entity=${entity.id}`}
                className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-100"
              >
                {t("check.ownerBtn")}
              </Link>
            </div>
          </div>
        </div>

        <RiskGauge score={risk.risk_score} factors={risk.factors} />

        {risk.is_under_dispute && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {t("check.disputeActive")}
          </p>
        )}

        {entity.owner_response && (
          <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4">
            <p className="text-xs font-bold text-blue-900">
              {t("check.pinnedOwner")}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-slate-700">{entity.owner_response}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric
            label={t("check.timesSearched")}
            value={search_intelligence?.total_searches_display ?? t("check.dash")}
            sub={t("check.totalLookups")}
          />
          <Metric
            label={t("check.searches7d")}
            value={String(search_intelligence?.searches_7d ?? 0)}
            sub={search_intelligence && search_intelligence.searches_7d > 0 ? t("check.velocitySpike") : t("check.dash")}
            accent="rose"
          />
          <Metric
            label={t("check.communityReports")}
            value={t("check.totalCount", { n: community.total_reports })}
            sub={t("check.adminVerified", { n: community.admin_verified_reports })}
          />
          <Metric
            label={t("check.lastQueried")}
            value={
              search_intelligence?.last_searched_at
                ? new Date(search_intelligence.last_searched_at).toLocaleDateString()
                : t("check.dash")
            }
            sub={t("check.activeThreat")}
          />
        </div>

        {ai_summary?.text && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wide text-blue-900">
                {t("check.aiSummary")}
              </span>
              <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                {ai_summary.grounded ? t("check.grounded") : t("check.ungrounded")}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-slate-700 sm:text-sm">{ai_summary.text}</p>
          </div>
        )}

        {related_fact_checks && related_fact_checks.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{t("check.relatedFactChecks")}</p>
            <ul className="mt-1 space-y-1 text-sm text-slate-700">
              {related_fact_checks.map((fc, i) => (
                <li key={i}>
                  <a href={fc.url ?? "#"} className="underline" target="_blank" rel="noreferrer">
                    {fc.text} {fc.rating ? `${t("check.dash")} ${fc.rating}` : ""}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <GovCheckBanner check={gov_check} />

        {(entity.merchant_name || meta?.merchant_name || entity.nmid) && (
          <dl className="space-y-1 text-sm text-slate-600">
            <Row k={t("check.merchant")} v={entity.merchant_name ?? meta?.merchant_name ?? null} />
            {entity.nmid && <Row k={t("check.nmid")} v={entity.nmid} />}
            {entity.mcc && <Row k={t("check.mcc")} v={entity.mcc} />}
          </dl>
        )}

        {meta?.homoglyph_warning && (
          <p className="text-sm text-amber-600">
            {t("check.lookalike")}
          </p>
        )}
        {meta?.qr_changed_since_last_seen && (
          <p className="text-sm text-rose-600">
            {t("check.qrChanged")}
          </p>
        )}

        <RedactedSlipViewer
          fields={{
            accountNumber: undefined,
            holderName: entity.holder?.name ?? "Not disclosed",
          }}
          allowAnalystView={false}
        />

        {reports.length > 0 && <ReportsFeed reports={reports} onFlag={onFlag} reportHref={reportHref} />}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-xs">
          <div className="flex items-center gap-2">
            <button
              onClick={onReport}
              className="rounded-lg bg-rose-600 px-3.5 py-2 font-bold text-white shadow-xs hover:bg-rose-700"
            >
              {t("check.reportThis")}
            </button>
            <Link
              href={`/receipt?country=${entity.country}&bank=${entity.institution ?? ""}&account=`}
              className="rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 font-bold text-slate-700 hover:bg-slate-100"
            >
              {t("check.exportReceipt")}
            </Link>
            <Link
              href={`/claim?entity=${entity.id}`}
              className="rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 font-bold text-blue-700 hover:bg-slate-100"
            >
              {t("check.fileClearance")}
            </Link>
          </div>
          <Link href="/recovery" className="font-bold text-rose-700 hover:underline">
            {t("check.alreadyPaid")}
          </Link>
        </div>
      </div>
    </div>
  );
}

function ReportsFeed({
  reports,
  onFlag,
  reportHref,
}: {
  reports: ReportView[];
  onFlag: (r: ReportView) => void;
  reportHref: string;
}) {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(reports.length / REPORTS_PER_PAGE));
  const start = (page - 1) * REPORTS_PER_PAGE;
  const slice = reports.slice(start, start + REPORTS_PER_PAGE);

  return (
    <div className="space-y-4 border-t border-slate-100 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wide text-slate-900">
            {t("check.reportsTitle", { n: reports.length })}
          </h3>
          <p className="text-xs text-slate-500">
            {t("check.showing", {
              from: start + 1,
              to: Math.min(start + REPORTS_PER_PAGE, reports.length),
              total: reports.length,
              page,
              pages: totalPages,
            })}
          </p>
        </div>
        <Link
          href={reportHref}
          className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-rose-700"
        >
          {t("check.addReport")}
        </Link>
      </div>

      <div className="space-y-3">
        {slice.map((r) => (
          <ReportCard key={r.id} report={r} onFlag={() => onFlag(r)} />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-200 pt-4 text-xs">
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("check.prevPage")}
          </button>
          <div className="flex items-center gap-1 font-semibold text-slate-700">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                onClick={() => setPage(n)}
                className={`h-7 w-7 rounded-lg ${
                  n === page
                    ? "bg-blue-600 font-bold text-white"
                    : "border border-slate-200 bg-white font-semibold text-slate-700 hover:bg-slate-50"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <button
            disabled={page === totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("check.nextPage")}
          </button>
        </div>
      )}
    </div>
  );
}

function ReportModal({
  country,
  bank,
  account,
  onClose,
}: {
  country: string;
  bank: string;
  account: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState(REPORT_CATEGORIES[0].value);
  const [severity, setSeverity] = useState(3);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [doneId, setDoneId] = useState<string | null>(null);
  const token = getToken();

  async function submit() {
    if (!consent) {
      setError(t("check.reportConsentRequired"));
      return;
    }
    setBusy(true);
    setError(null);
    const payload = {
      target: { kind: "ACCOUNT" as const, country, bank, account },
      category,
      severity,
      description,
      currency: "IDR",
      loss_amount: amount ? Number(amount) : null,
      consent,
    };
    try {
      if (token) {
        const created = await createReport(token, payload);
        setDoneId(created.report_id);
      } else {
        if (!name.trim() || !email.trim()) {
          setError(t("report.reporterRequired"));
          setBusy(false);
          return;
        }
        const created = await createAnonymousReport({
          ...payload,
          reporter_name: name.trim(),
          reporter_email: email.trim(),
        });
        if (created.access_token) setToken(created.access_token);
        setDoneId(created.report_id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("report.submitError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900">{t("check.reportModalTitle")}</h3>
            <p className="font-mono text-[11px] text-slate-500">
              {country} · {bank} · {account || "—"}
            </p>
          </div>
          <button onClick={onClose} className="text-lg text-slate-400 hover:text-slate-600">
            ✕
          </button>
        </div>

        {doneId ? (
          <div className="space-y-3 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-emerald-200 bg-emerald-100 text-xl font-bold text-emerald-700">
              ✓
            </div>
            <p className="text-sm font-semibold text-slate-800">{t("check.reportSuccess")}</p>
            <p className="text-xs text-slate-500">
              {t("report.reference")} <span className="font-mono font-bold text-slate-800">{doneId}</span>
            </p>
            <button
              onClick={onClose}
              className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700"
            >
              {t("common.close")}
            </button>
          </div>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-slate-600">{t("check.reportModalDesc")}</p>

            {!token && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <MiniLabel>{t("report.reporterName")}</MiniLabel>
                  <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder={t("report.reporterNamePlaceholder")} />
                </div>
                <div>
                  <MiniLabel>{t("report.reporterEmail")}</MiniLabel>
                  <input className={inputCls} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("common.email")} />
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <MiniLabel>{t("report.category")}</MiniLabel>
                <select className={inputCls} value={category} onChange={(e) => setCategory(e.target.value)}>
                  {REPORT_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {t(`cat.${c.value}`)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <MiniLabel>{t("report.severity")}</MiniLabel>
                <select className={inputCls} value={severity} onChange={(e) => setSeverity(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((s) => (
                    <option key={s} value={s}>
                      {t("report.severityOption", { n: s })}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <MiniLabel>{t("report.lossAmount")} ({t("common.optional")})</MiniLabel>
              <input
                className={`${inputCls} font-mono`}
                inputMode="numeric"
                value={amount}
                onChange={(e) => setAmount(e.target.value.replace(/[^\d]/g, ""))}
                placeholder="1500000"
              />
            </div>

            <div>
              <MiniLabel>{t("report.narrative")}</MiniLabel>
              <textarea
                className={inputCls}
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("report.narrativePlaceholder")}
              />
            </div>

            <label className="flex cursor-pointer items-start gap-2 text-[11px] text-slate-600">
              <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-blue-600" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>{t("report.declaration")}</span>
            </label>

            {error && <p className="text-xs text-rose-600">{error}</p>}

            <div className="flex gap-2 pt-1">
              <button onClick={onClose} className="flex-1 rounded-lg bg-slate-100 py-2 text-xs font-bold text-slate-700">
                {t("common.cancel")}
              </button>
              <button
                onClick={() => void submit()}
                disabled={busy || description.length < 20}
                className="flex-1 rounded-lg bg-rose-600 py-2 text-xs font-bold text-white shadow-xs hover:bg-rose-700 disabled:opacity-50"
              >
                {busy ? t("report.submitting") : t("report.submit")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function FlagModal({ report, onClose }: { report: ReportView; onClose: () => void }) {
  const { t } = useI18n();
  const token = getToken();
  const [reason, setReason] = useState(FLAG_REASONS[0].value);
  const [details, setDetails] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!token) {
      setError(t("check.flagError"));
      return;
    }
    try {
      const flag = await flagReport(token, report.id, reason, details || undefined);
      setStatus(flag.status);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("check.flagFailed"));
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900">{t("check.flagModalTitle")}</h3>
            <p className="font-mono text-[11px] text-slate-500">{t("check.reportLabel")} {report.id.slice(0, 8)}</p>
          </div>
          <button onClick={onClose} className="text-lg text-slate-400 hover:text-slate-600">
            ✕
          </button>
        </div>

        {status ? (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            {t("check.flagSubmitted", { status })}
          </p>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-slate-600">
              {t("check.flagModalDesc")}
            </p>
            <div>
              <label className="mb-1 block text-xs font-bold text-slate-700">
                {t("check.whyTakenDown")}
              </label>
              <select
                className={inputCls}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
                {FLAG_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {t(`flag.${r.value}`)}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              rows={3}
              className={inputCls}
              placeholder={t("check.explanation")}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
            {error && <p className="text-xs text-rose-600">{error}</p>}
          </>
        )}

        <div className="flex gap-2 pt-2">
          <button onClick={onClose} className="flex-1 rounded-lg bg-slate-100 py-2 text-xs font-bold text-slate-700">
            {t("common.close")}
          </button>
          {!status && (
            <button
              onClick={() => void submit()}
              className="flex-1 rounded-lg bg-blue-600 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700"
            >
              {t("check.submitFlag")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: "rose";
}) {
  const { t } = useI18n();
  void t;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3.5">
      <span className="text-[11px] font-bold uppercase text-slate-500">{label}</span>
      <p className={`mt-0.5 text-xl font-extrabold ${accent === "rose" ? "text-rose-600" : "text-slate-900"}`}>
        {value}
      </p>
      <span className={`text-[10px] ${accent === "rose" ? "font-semibold text-rose-600" : "text-slate-400"}`}>
        {sub}
      </span>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string | null }) {
  const { t } = useI18n();
  void t;
  if (!v) return null;
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  );
}

function WatchButton({ entityId }: { entityId: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<"idle" | "saving" | "done">("idle");
  const token = getToken();
  if (!token) {
    return (
      <Link
        href="/profile"
        className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"
      >
        {t("check.watchSignin")}
      </Link>
    );
  }
  return (
    <button
      disabled={state !== "idle"}
      onClick={async () => {
        setState("saving");
        try {
          await addWatch(token, entityId);
          setState("done");
        } catch {
          setState("idle");
        }
      }}
      className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-60"
    >
      {state === "done" ? t("check.watching") : t("check.watchAccount")}
    </button>
  );
}

function GovCheckBanner({ check }: { check?: { source: string; available: boolean; found: boolean; report_count: number; category?: string } | null }) {
  const { t } = useI18n();
  if (!check || !check.available) return null;
  const kind = check.category === "phone" ? t("check.kindPhone") : t("check.kindAccount");
  if (check.found) {
    return (
      <div className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-800">
        <p className="font-semibold">{t("check.govMatch", { source: check.source })}</p>
        <p className="mt-0.5">
          {t("check.govMatchBody", { kind, n: check.report_count })}
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
      {t("check.govClean", { source: check.source })}
    </div>
  );
}

function PhoneResultCard({ data }: { data: PhoneSearchResult }) {
  const { t } = useI18n();
  const found = data.wallet_count > 0;
  const band = riskBand(data.totals.max_risk_score);
  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      <div className="flex items-center justify-between">
        <p className="font-mono text-lg font-bold text-slate-900">{data.phone_masked}</p>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${band.badge}`}>
          {t("check.wallets", { n: data.wallet_count })}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        {data.country} · {t("check.maxRisk")} {data.totals.max_risk_score} · {t(band.labelKey)}
        {found ? "" : ` · ${t("check.noReports")}`}
      </p>

      <GovCheckBanner check={data.gov_check} />

      {found ? (
        <ul className="mt-3 space-y-2">
          {data.wallets.map((w) => (
            <li
              key={`${w.institution}-${w.account_masked}`}
              className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-800">
                  {w.institution_name ?? w.institution}
                </span>
                <span className="text-xs text-slate-500">
                  {t("check.riskInline", { n: w.risk_score })} ·{" "}
                  {t("check.reportsInline", { n: w.total_reports })}
                </span>
              </div>
              <p className="mt-0.5 font-mono text-xs text-slate-500">{w.account_masked}</p>
              {w.is_gov_blacklisted && (
                <p className="mt-1 text-xs text-rose-600">{t("check.govBlacklist")}</p>
              )}
              {w.is_under_dispute && (
                <p className="mt-1 text-xs text-amber-600">{t("check.disputeActiveShort")}</p>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-500">{t("check.noWalletReports")}</p>
      )}
    </div>
  );
}
