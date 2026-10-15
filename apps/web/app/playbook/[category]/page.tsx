"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getPlaybook, type PlaybookEntry } from "@/lib/api";
import { useI18n } from "@/components/LocaleProvider";

export default function PlaybookDetail() {
  const { t } = useI18n();
  const params = useParams<{ category: string }>();
  const category = params?.category;
  const [entry, setEntry] = useState<PlaybookEntry | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!category) return;
    void getPlaybook(category)
      .then(setEntry)
      .catch(() => setNotFound(true));
  }, [category]);

  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col gap-4 px-6 py-12">
      <Link href="/playbook" className="text-xs font-medium text-slate-500 hover:text-blue-600">
        ← {t("playbook.title")}
      </Link>
      {notFound && <p className="text-rose-600">{t("playbook.unknown")}</p>}
      {entry && (
        <>
          <h1 className="text-2xl font-bold text-slate-900">{entry.title}</h1>
          <p className="text-slate-600">{entry.summary}</p>

          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
            <p className="text-sm font-semibold text-rose-800">{t("playbook.redFlags")}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-700">
              {entry.red_flags.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm font-semibold text-emerald-800">{t("playbook.beforePay")}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-emerald-700">
              {entry.checklist.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>

          <Link
            href="/check"
            className="rounded-lg bg-blue-600 px-4 py-2 text-center font-semibold text-white shadow-xs hover:bg-blue-700"
          >
            {t("playbook.checkNow")}
          </Link>
        </>
      )}
    </main>
  );
}
