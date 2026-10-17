"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getMe, getToken, setToken, type Me } from "@/lib/api";
import { useI18n } from "./LocaleProvider";

const ADMIN_ROLES = new Set(["ANALYST", "SENIOR_ANALYST", "SUPERADMIN"]);

/** Header auth control: Sign in when signed out; avatar + profile/admin + sign
 *  out when signed in. */
export function AuthMenu() {
  const { t } = useI18n();
  const [me, setMe] = useState<Me | null>(null);
  const [token, setTok] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const tk = getToken();
    setTok(tk);
    setReady(true);
    if (tk) {
      getMe(tk)
        .then(setMe)
        .catch(() => {
          setToken(null);
          setTok(null);
        });
    }
  }, []);

  if (!ready) return null;

  if (!token) {
    return (
      <Link
        href="/profile"
        className="hidden rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 sm:inline-block"
      >
        {t("nav.signIn")}
      </Link>
    );
  }

  const initial = (me?.display_name || me?.email || "?").slice(0, 1).toUpperCase();
  return (
    <div className="flex items-center gap-2">
      {me && ADMIN_ROLES.has(me.role) && (
        <Link
          href="/admin"
          className="hidden rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-100 sm:inline-block"
        >
          {t("nav.admin")}
        </Link>
      )}
      <Link
        href="/profile"
        title={me?.display_name ?? me?.email ?? ""}
        className="flex items-center gap-2 rounded-lg border border-slate-300 px-2 py-1.5 hover:bg-slate-100"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-[11px] font-bold text-white">
          {initial}
        </span>
        <span className="hidden max-w-[10rem] truncate text-xs font-semibold text-slate-700 sm:inline">
          {me?.display_name ?? me?.email}
        </span>
      </Link>
      <button
        onClick={() => {
          setToken(null);
          window.location.href = "/";
        }}
        className="text-xs font-semibold text-slate-500 underline hover:text-slate-800"
      >
        {t("common.signOut")}
      </button>
    </div>
  );
}
