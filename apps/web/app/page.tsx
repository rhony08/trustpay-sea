"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BANKS, COUNTRIES } from "@/lib/api";
import { ShieldMark } from "@/components/Brand";
import { useI18n } from "@/components/LocaleProvider";

type Tab = "account" | "phone" | "qr";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

export default function HomePage() {
  const router = useRouter();
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("account");
  const [country, setCountry] = useState("ID");
  const [bank, setBank] = useState(BANKS.ID[0].code);
  const [account, setAccount] = useState("");
  const [nameClaim, setNameClaim] = useState("");
  const [phoneCountry, setPhoneCountry] = useState("ID");
  const [phone, setPhone] = useState("");
  const [qrPayload, setQrPayload] = useState("");

  function submitAccount(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams({ country, bank, account });
    if (nameClaim) params.set("nameClaim", nameClaim);
    router.push(`/check?${params.toString()}`);
  }

  function submitPhone(e: React.FormEvent) {
    e.preventDefault();
    router.push(`/check?tab=phone&country=${phoneCountry}&phone=${encodeURIComponent(phone)}`);
  }

  function submitQr() {
    if (!qrPayload) return;
    router.push(`/check?tab=qr&payload=${encodeURIComponent(qrPayload)}`);
  }

  return (
    <main className="flex-1">
      <section className="relative overflow-hidden border-b border-slate-200 bg-white pb-16 pt-12 lg:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-7">
              <span className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">
                <span className="h-2 w-2 rounded-full bg-blue-600" />
                {t("home.badge")}
              </span>

              <h1 className="text-4xl font-black leading-tight tracking-tight text-slate-900 sm:text-5xl">
                {t("home.title1")} <br className="hidden sm:inline" />
                <span className="text-blue-600">{t("home.title2")}</span>
              </h1>

              <p className="max-w-xl text-base leading-relaxed text-slate-600 sm:text-lg">
                {t("home.subtitle")}
              </p>

              <div className="rounded-2xl border-2 border-slate-200 bg-white p-5 shadow-xl sm:p-6">
                <div className="mb-5 flex border-b border-slate-200">
                  <TabButton active={tab === "account"} onClick={() => setTab("account")}>
                    {t("home.tabBank")}
                  </TabButton>
                  <TabButton active={tab === "phone"} onClick={() => setTab("phone")}>
                    {t("home.tabPhone")}
                  </TabButton>
                  <TabButton active={tab === "qr"} onClick={() => setTab("qr")}>
                    {t("home.tabQr")}
                  </TabButton>
                </div>

                {tab === "account" ? (
                  <form className="space-y-4" onSubmit={submitAccount}>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div>
                        <Label>{t("home.country")}</Label>
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
                              {c.label} ({c.code})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <Label>{t("home.bank")}</Label>
                        <select
                          className={inputCls}
                          value={bank}
                          onChange={(e) => setBank(e.target.value)}
                        >
                          {(BANKS[country] ?? []).map((b) => (
                            <option key={b.code} value={b.code}>
                              {b.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <Label>{t("home.accountNumber")}</Label>
                      <input
                        inputMode="numeric"
                        required
                        placeholder={t("home.accountPlaceholder")}
                        className={`${inputCls} font-mono text-base`}
                        value={account}
                        onChange={(e) => setAccount(e.target.value)}
                      />
                    </div>

                    <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-3.5">
                      <div className="mb-1 flex items-center justify-between">
                        <label className="flex items-center gap-1.5 text-xs font-bold text-blue-900">
                          {t("home.nameMatcher")}
                        </label>
                        <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                          {t("home.recommended")}
                        </span>
                      </div>
                      <input
                        placeholder={t("home.nameMatcherPlaceholder")}
                        className="w-full rounded-lg border border-blue-200 bg-white px-3 py-1.5 text-xs text-slate-800 outline-none focus:border-blue-500"
                        value={nameClaim}
                        onChange={(e) => setNameClaim(e.target.value)}
                      />
                      <p className="mt-1.5 text-[11px] text-blue-800">
                        {t("home.nameMatcherHelp")}
                      </p>
                    </div>

                    <button
                      type="submit"
                      className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-blue-700"
                    >
                      <ShieldMark className="h-5 w-5" />
                      {t("home.checkAccountBtn")}
                    </button>
                  </form>
                ) : tab === "phone" ? (
                  <form className="space-y-4" onSubmit={submitPhone}>
                    <div>
                      <Label>{t("home.phoneLabel")}</Label>
                      <div className="flex gap-2">
                        <select
                          className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium"
                          value={phoneCountry}
                          onChange={(e) => setPhoneCountry(e.target.value)}
                        >
                          {["ID", "MY", "SG", "TH", "PH"].map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                        <input
                          type="tel"
                          required
                          placeholder={t("home.phonePlaceholder")}
                          className="flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-base outline-none focus:border-blue-600"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                        />
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        {t("home.phoneHelp")}
                      </p>
                    </div>
                    <button
                      type="submit"
                      className="w-full rounded-xl bg-blue-600 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-blue-700"
                    >
                      {t("home.checkWalletBtn")}
                    </button>
                  </form>
                ) : (
                  <div className="space-y-4">
                    <label className="block cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center hover:border-blue-500">
                      <ShieldMark className="mx-auto mb-2 h-10 w-10 text-slate-400" />
                      <p className="text-sm font-bold text-slate-700">
                        {t("home.qrUploadTitle")}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {t("home.qrUploadHelp")}
                      </p>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) {
                            const params = new URLSearchParams({ tab: "qr", qrFile: f.name });
                            router.push(`/check?${params.toString()}`);
                          }
                        }}
                      />
                    </label>
                    <div className="text-center text-xs font-bold uppercase text-slate-400">
                      {t("home.qrOrPaste")}
                    </div>
                    <input
                      placeholder={t("home.qrPlaceholder")}
                      className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs"
                      value={qrPayload}
                      onChange={(e) => setQrPayload(e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={submitQr}
                      className="w-full rounded-xl bg-blue-600 py-3.5 text-sm font-bold text-white shadow-md hover:bg-blue-700"
                    >
                      {t("home.checkQrBtn")}
                    </button>
                  </div>
                )}

                <div className="mt-4 flex flex-wrap items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5 font-medium">
                    {t("home.seeded")}
                  </span>
                  <span className="flex items-center gap-1.5 font-medium">{t("home.kms")}</span>
                </div>
              </div>
            </div>

            <div className="flex justify-center lg:col-span-5">
              <PhoneMockup />
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-200 bg-slate-100 py-8">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <p className="mb-5 text-center text-xs font-bold uppercase tracking-wider text-slate-500">
            {t("home.proofTitle")}
          </p>
          <div className="grid grid-cols-2 gap-4 text-center sm:grid-cols-4">
            <ProofCard title={t("home.proof1Title")} body={t("home.proof1Body")} />
            <ProofCard title={t("home.proof2Title")} body={t("home.proof2Body")} />
            <ProofCard title={t("home.proof3Title")} body={t("home.proof3Body")} />
            <ProofCard title={t("home.proof4Title")} body={t("home.proof4Body")} />
          </div>
        </div>
      </section>

      <section className="border-b border-slate-200 bg-white py-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="mx-auto mb-12 max-w-2xl text-center">
            <h2 className="mb-3 text-2xl font-extrabold text-slate-900 sm:text-3xl">
              {t("home.pillarsTitle")}
            </h2>
            <p className="text-sm text-slate-600">
              {t("home.pillarsSub")}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <Pillar
              n="1"
              tone="blue"
              title={t("home.pillar1Title")}
              body={t("home.pillar1Body")}
              href="/check"
              cta={t("home.pillar1Cta")}
            />
            <Pillar
              n="2"
              tone="rose"
              title={t("home.pillar2Title")}
              body={t("home.pillar2Body")}
              href="/report"
              cta={t("home.pillar2Cta")}
            />
            <Pillar
              n="3"
              tone="emerald"
              title={t("home.pillar3Title")}
              body={t("home.pillar3Body")}
              href="/claim"
              cta={t("home.pillar3Cta")}
            />
          </div>
        </div>
      </section>
    </main>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-bold text-slate-700">{children}</label>;
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 px-4 pb-3 text-sm ${
        active
          ? "border-b-2 border-blue-600 font-bold text-blue-600"
          : "font-semibold text-slate-500 hover:text-slate-800"
      }`}
    >
      {children}
    </button>
  );
}

function ProofCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
      <p className="text-xs font-bold text-slate-900">{title}</p>
      <p className="mt-1 text-[11px] text-slate-500">{body}</p>
    </div>
  );
}

const TONES = {
  blue: "bg-blue-100 text-blue-700",
  rose: "bg-rose-100 text-rose-700",
  emerald: "bg-emerald-100 text-emerald-700",
} as const;

const CTA = {
  blue: "text-blue-600 hover:text-blue-800",
  rose: "text-rose-600 hover:text-rose-800",
  emerald: "text-emerald-600 hover:text-emerald-800",
} as const;

function Pillar({
  n,
  tone,
  title,
  body,
  href,
  cta,
}: {
  n: string;
  tone: keyof typeof TONES;
  title: string;
  body: string;
  href: string;
  cta: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/50 p-6 transition-all hover:bg-white hover:shadow-md">
      <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl text-lg font-bold ${TONES[tone]}`}>
        {n}
      </div>
      <h3 className="mb-2 text-base font-bold text-slate-900">{title}</h3>
      <p className="mb-4 text-xs leading-relaxed text-slate-600">{body}</p>
      <Link href={href} className={`text-xs font-bold ${CTA[tone]}`}>
        {cta} &rarr;
      </Link>
    </div>
  );
}

function PhoneMockup() {
  const { t } = useI18n();
  return (
    <div className="relative w-full max-w-sm">
      <div className="absolute -inset-4 rotate-2 rounded-3xl bg-gradient-to-r from-blue-100 to-indigo-100 blur-sm" />
      <div className="relative space-y-4 rounded-3xl border-4 border-slate-900 bg-white p-5 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-500" />
            <span className="h-3 w-3 rounded-full bg-amber-500" />
            <span className="h-3 w-3 rounded-full bg-emerald-500" />
          </div>
          <span className="font-mono text-[10px] font-bold text-slate-400">{t("home.mockHeader")}</span>
        </div>

        <div className="space-y-2 rounded-2xl border-2 border-red-300 bg-red-50 p-4 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-600 text-xl font-bold text-white shadow-md">
            !
          </div>
          <span className="rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-white">
            {t("home.mockCritical")}
          </span>
          <h4 className="text-base font-extrabold leading-tight text-slate-900">{t("home.mockAccount")}</h4>
          <p className="text-xs font-bold text-red-800">{t("home.mockRecipient")}</p>
          <p className="text-[11px] text-slate-600">
            {t("home.mockReports")}
            <br />
            {t("home.mockClaimed")} <b>&ldquo;Siti Aminah&rdquo;</b>
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2 text-center text-xs">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-2.5">
            <span className="text-[10px] font-bold uppercase text-slate-500">{t("home.mockRiskScore")}</span>
            <p className="text-lg font-black text-red-600">{t("home.mockRiskValue")}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-2.5">
            <span className="text-[10px] font-bold uppercase text-slate-500">{t("home.mockSearched")}</span>
            <p className="text-lg font-black text-slate-900">{t("home.mockSearchedValue")}</p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs font-medium text-emerald-900">
          <span className="shrink-0 text-emerald-600">✓</span>
          <span>{t("home.mockProtected")}</span>
        </div>
      </div>
    </div>
  );
}
