"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  BANKS,
  REPORT_CATEGORIES,
  createAnonymousReport,
  createReport,
  getReport,
  getToken,
  listBanks,
  setToken,
  uploadEvidence,
  type Bank,
  type ReportForensics,
} from "@/lib/api";
import { RedactedSlipViewer } from "@/components/RedactedSlipViewer";
import { AiForensics } from "@/components/AiForensics";
import { BankPicker } from "@/components/BankPicker";
import { useI18n } from "@/components/LocaleProvider";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

const STATUS_STYLES: Record<string, string> = {
  PROCESSING: "border-amber-200 bg-amber-50 text-amber-800",
  PUBLISHED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  FAILED: "border-rose-200 bg-rose-50 text-rose-800",
};

function fallbackBanks(country: string): Bank[] {
  return (BANKS[country] ?? []).map((b) => ({
    country,
    code: b.code,
    name: b.name,
    short_name: b.name,
    bank_type: "COMMERCIAL",
    bic: null,
    national_id: null,
  }));
}

const STEPS = ["report.step1", "report.step2", "report.step3", "report.step4"];

export default function ReportPage() {
  const { t } = useI18n();
  const [token, setTokenState] = useState<string | null>(null);
  const [anonName, setAnonName] = useState("");
  const [anonEmail, setAnonEmail] = useState("");

  const [step, setStep] = useState(1);
  const [country, setCountry] = useState("ID");
  const [banks, setBanks] = useState<Bank[]>([]);
  const [bank, setBank] = useState("014");
  const [account, setAccount] = useState("");
  const [claimedName, setClaimedName] = useState("");
  const [category, setCategory] = useState(REPORT_CATEGORIES[0].value);
  const [severity, setSeverity] = useState(3);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("IDR");
  const [incidentDate, setIncidentDate] = useState("");
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  const [policeRef, setPoliceRef] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [reportStatus, setReportStatus] = useState<string | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState<string | null>(null);
  const [forensics, setForensics] = useState<ReportForensics | null>(null);

  useEffect(() => setTokenState(getToken()), []);

  // Prefill the target from the dossier's "Add report" link (?country&bank&account).
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const c = sp.get("country");
    const b = sp.get("bank");
    const a = sp.get("account");
    if (c) setCountry(c);
    if (b) setBank(b);
    if (a) setAccount(a);
  }, []);

  // Full institution directory (country-optional picker).
  useEffect(() => {
    void listBanks()
      .then((rows) => setBanks(rows.length ? rows : fallbackBanks("ID")))
      .catch(() => setBanks(fallbackBanks("ID")));
  }, []);

  async function poll(id: string) {
    for (let i = 0; i < 20; i += 1) {
      await new Promise((r) => setTimeout(r, 1500));
      const view = await getReport(id);
      setReportStatus(view.processing_status);
      setEvidenceUrl(view.evidence?.[0]?.media_url ?? null);
      setForensics(view.forensics ?? null);
      if (view.processing_status !== "PROCESSING") return;
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setReportStatus(null);
    setEvidenceUrl(null);
    setForensics(null);
    const payload = {
      target: { kind: "ACCOUNT" as const, country, bank, account },
      category,
      severity,
      description,
      currency,
      loss_amount: amount ? Number(amount) : null,
      incident_date: incidentDate || null,
      consent,
    };
    try {
      let uploadToken = token;
      let createdId: string;
      let createdStatus: string;
      if (token) {
        const created = await createReport(token, payload);
        createdId = created.report_id;
        createdStatus = created.processing_status;
      } else {
        if (!anonName.trim() || !anonEmail.trim()) {
          setError(t("report.reporterRequired"));
          setBusy(false);
          return;
        }
        const created = await createAnonymousReport({
          ...payload,
          reporter_email: anonEmail.trim(),
          reporter_name: anonName.trim(),
        });
        createdId = created.report_id;
        createdStatus = created.processing_status;
        if (created.access_token) {
          setToken(created.access_token);
          setTokenState(created.access_token);
        }
        // Report-scoped token → evidence upload works even for a registered email.
        uploadToken = created.evidence_token ?? created.access_token ?? null;
      }
      if (file && uploadToken) {
        try {
          await uploadEvidence(uploadToken, createdId, file);
        } catch {
          /* evidence is optional; the report itself is already submitted */
        }
      }
      setReportId(createdId);
      setReportStatus(createdStatus);
      void poll(createdId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("report.submitError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex-1 py-10">
      <div className="mx-auto max-w-2xl px-4 sm:px-6">
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 sm:text-3xl">{t("report.title")}</h1>
            <p className="mt-1 text-xs text-slate-600 sm:text-sm">{t("report.subtitle")}</p>
          </div>
          {token ? (
            <button
              onClick={() => {
                setToken(null);
                setTokenState(null);
              }}
              className="self-start text-sm text-slate-400 underline"
            >
              {t("common.signOut")}
            </button>
          ) : (
            <span className="self-start whitespace-nowrap rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              {t("report.noAccountNeeded")}
            </span>
          )}
        </div>

        {!reportStatus && (
          <div className="mb-8 flex items-center justify-between border-b border-slate-200 pb-4 text-xs font-bold text-slate-500">
            {STEPS.map((label, i) => {
              const n = i + 1;
              const done = step > n;
              const active = step === n;
              return (
                <div key={label} className="flex flex-1 items-center gap-2">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      active || done
                        ? "border border-blue-400 bg-blue-100 text-blue-800"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {n}
                  </span>
                  <span className={`hidden sm:inline ${active ? "text-blue-700" : ""}`}>{t(label)}</span>
                  {n < STEPS.length && <span className="hidden h-0.5 flex-1 bg-slate-200 sm:block" />}
                </div>
              );
            })}
          </div>
        )}

        <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs sm:p-8">
          {reportStatus ? (
            <SuccessPanel
              status={reportStatus}
              reportId={reportId}
              evidenceUrl={evidenceUrl}
              forensics={forensics}
            />
          ) : step === 1 ? (
            <>
              <h2 className="text-base font-bold text-slate-900">{t("report.s1Title")}</h2>
              <div>
                <Label>{t("report.bank")}</Label>
                <BankPicker
                  banks={banks}
                  value={`${country}:${bank}`}
                  onChange={(b) => {
                    setBank(b.code);
                    setCountry(b.country);
                  }}
                  inputClassName={inputCls}
                />
              </div>
              <div>
                <Label>{t("report.account")}</Label>
                <input
                  className={`${inputCls} font-mono font-bold`}
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder={t("report.accountPlaceholder")}
                />
                <p className="mt-1 text-[11px] text-slate-500">{t("report.accountHelp")}</p>
              </div>
              <div>
                <Label>{t("report.claimed")}</Label>
                <input
                  className={inputCls}
                  value={claimedName}
                  onChange={(e) => setClaimedName(e.target.value)}
                  placeholder={t("report.claimedPlaceholder")}
                />
                <p className="mt-1 text-[11px] text-slate-500">{t("report.claimedHelp")}</p>
              </div>
              <div className="flex justify-end pt-2">
                <NextButton disabled={!account} onClick={() => setStep(2)}>
                  {t("report.continueLoss")}
                </NextButton>
              </div>
            </>
          ) : step === 2 ? (
            <>
              <h2 className="text-base font-bold text-slate-900">{t("report.s2Title")}</h2>
              <div>
                <Label>{t("report.category")}</Label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {REPORT_CATEGORIES.map((c) => (
                    <label
                      key={c.value}
                      className={`flex cursor-pointer items-center gap-2.5 rounded-xl border p-3 text-xs ${
                        category === c.value
                          ? "border-blue-400 bg-blue-50"
                          : "border-slate-200 bg-slate-50 hover:border-blue-300 hover:bg-white"
                      }`}
                    >
                      <input
                        type="radio"
                        name="cat"
                        className="accent-blue-600"
                        checked={category === c.value}
                        onChange={() => setCategory(c.value)}
                      />
                      <span>{t(`cat.${c.value}`)}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <Label>{t("report.lossAmount")}</Label>
                  <div className="flex">
                    <select
                      className="rounded-l-lg border border-r-0 border-slate-300 bg-slate-100 px-2 text-xs font-bold text-slate-600"
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                    >
                      {["IDR", "MYR", "SGD", "THB", "VND", "PHP"].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      className="flex-1 rounded-r-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-sm font-bold"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="1500000"
                    />
                  </div>
                </div>
                <div>
                  <Label>{t("report.txnDate")}</Label>
                  <input type="date" className={inputCls} value={incidentDate} onChange={(e) => setIncidentDate(e.target.value)} />
                </div>
                <div>
                  <Label>{t("report.severity")}</Label>
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
                <Label>{t("report.narrative")}</Label>
                <textarea
                  rows={3}
                  className={inputCls}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("report.narrativePlaceholder")}
                />
              </div>
              <div className="flex justify-between pt-2">
                <BackButton onClick={() => setStep(1)} />
                <NextButton disabled={description.length < 20} onClick={() => setStep(3)}>
                  {t("report.continueSlip")}
                </NextButton>
              </div>
            </>
          ) : step === 3 ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-900">{t("report.s3Title")}</h2>
                <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  {t("report.failClosed")}
                </span>
              </div>
              <label className="block cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center hover:border-blue-500">
                <span className="mb-1 block text-3xl">🧾</span>
                <p className="text-sm font-bold text-slate-800">
                  {file ? file.name : t("report.uploadTitle")}
                </p>
                <p className="mt-1 text-xs text-slate-500">{t("report.uploadHelp")}</p>
                <input type="file" accept="image/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </label>
              <div className="space-y-3 rounded-xl border border-blue-200 bg-blue-50/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wide text-blue-900">
                    {t("report.howProtect")}
                  </span>
                  <span className="rounded bg-blue-200 px-1.5 py-0.5 text-[10px] font-bold text-blue-900">ADR-016</span>
                </div>
                <p className="text-xs leading-relaxed text-slate-600">{t("report.howProtectBody")}</p>
              </div>
              <RedactedSlipViewer allowAnalystView />
              <div className="flex justify-between pt-2">
                <BackButton onClick={() => setStep(2)} />
                <NextButton onClick={() => setStep(4)}>{t("report.continueDeclaration")}</NextButton>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-base font-bold text-slate-900">{t("report.s4Title")}</h2>
              {!token && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <Label>{t("report.reporterName")}</Label>
                    <input
                      className={inputCls}
                      value={anonName}
                      onChange={(e) => setAnonName(e.target.value)}
                      placeholder={t("report.reporterNamePlaceholder")}
                      required
                    />
                  </div>
                  <div>
                    <Label>{t("report.reporterEmail")}</Label>
                    <input
                      className={inputCls}
                      type="email"
                      value={anonEmail}
                      onChange={(e) => setAnonEmail(e.target.value)}
                      placeholder={t("common.email")}
                      required
                    />
                  </div>
                  <p className="text-[11px] text-slate-500 sm:col-span-2">{t("report.reporterHelp")}</p>
                </div>
              )}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-700">
                <label className="flex cursor-pointer items-start gap-2.5">
                  <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-blue-600" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                  <span>{t("report.declaration")}</span>
                </label>
              </div>
              <div>
                <Label>{t("report.policeRef")}</Label>
                <input className={inputCls} value={policeRef} onChange={(e) => setPoliceRef(e.target.value)} placeholder={t("report.policeRefPlaceholder")} />
              </div>
              {error && <p className="text-sm text-rose-600">{error}</p>}
              <div className="flex justify-between pt-2">
                <BackButton onClick={() => setStep(3)} />
                <button
                  disabled={busy || !consent}
                  onClick={() => void submit()}
                  className="rounded-xl bg-rose-600 px-6 py-2.5 text-sm font-bold text-white shadow-xs hover:bg-rose-700 disabled:opacity-50"
                >
                  {busy ? t("report.submitting") : t("report.submit")}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-bold text-slate-700">{children}</label>;
}

function NextButton({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white shadow-xs transition-colors hover:bg-blue-700 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  const { t } = useI18n();
  return (
    <button onClick={onClick} className="rounded-xl border border-slate-300 bg-slate-50 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100">
      {t("common.back")}
    </button>
  );
}

function SuccessPanel({
  status,
  reportId,
  evidenceUrl,
  forensics,
}: {
  status: string;
  reportId: string | null;
  evidenceUrl: string | null;
  forensics: ReportForensics | null;
}) {
  const { t } = useI18n();
  return (
    <div className="space-y-4 py-4 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-emerald-200 bg-emerald-100 text-2xl font-bold text-emerald-700">
        ✓
      </div>
      <h2 className="text-xl font-bold text-slate-900">
        {status === "PUBLISHED"
          ? t("report.published")
          : status === "PROCESSING"
            ? t("report.processingTitle")
            : t("report.submittedTitle")}
      </h2>
      <p className="mx-auto max-w-md text-xs text-slate-600">
        {status === "PROCESSING"
          ? t("report.processingBody")
          : status === "PUBLISHED"
            ? t("report.publishedBody")
            : t("report.failedBody")}
      </p>
      <p className="text-xs text-slate-500">
        {t("report.reference")} <span className="font-mono font-bold text-slate-800">{reportId}</span>
      </p>
      <span className={`inline-block rounded-full border px-3 py-1 text-xs font-semibold ${STATUS_STYLES[status] ?? STATUS_STYLES.PROCESSING}`}>
        {status}
      </span>
      {status === "PUBLISHED" && <AiForensics forensics={forensics} />}
      {status === "PUBLISHED" && evidenceUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={evidenceUrl} alt={t("report.evidenceAlt")} className="mx-auto mt-3 max-h-64 rounded-lg border border-slate-200" />
      )}
      <div className="flex flex-wrap justify-center gap-3 pt-2">
        <Link href="/check" className="rounded-xl bg-blue-600 px-5 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700">
          {t("report.viewResult")}
        </Link>
        <Link href="/recovery" className="rounded-xl border border-slate-200 bg-slate-100 px-5 py-2 text-xs font-bold text-slate-700 hover:bg-slate-200">
          {t("report.openFreeze")}
        </Link>
      </div>
    </div>
  );
}
