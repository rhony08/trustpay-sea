"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  enrollPasskey,
  eraseData,
  exportData,
  getNotifications,
  getProfile,
  getQuiz,
  getToken,
  getWatchlist,
  listPasskeys,
  login,
  markNotificationRead,
  removeWatch,
  setToken,
  signup,
  submitQuiz,
  verifyPhoneConfirm,
  verifyPhoneStart,
  type NotificationItem,
  type QuizQuestion,
  type TrustProfile,
  type WatchlistItem,
} from "@/lib/api";

const input =
  "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-slate-800 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

const TIER_STYLES: Record<string, string> = {
  NEWCOMER: "border-slate-300 text-slate-600",
  CONTRIBUTOR: "border-sky-300 text-sky-700",
  TRUSTED: "border-emerald-300 text-emerald-700",
  GUARDIAN: "border-amber-300 text-amber-700",
};

const card = "rounded-xl border border-slate-200 bg-white p-5 shadow-xs";

export default function ProfilePage() {
  const [token, setTokenState] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signup" | "login">("signup");
  const [error, setError] = useState<string | null>(null);

  const [profile, setProfile] = useState<TrustProfile | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<number[]>([]);
  const [quizResult, setQuizResult] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [passkeys, setPasskeys] = useState<{ credential_id: string; created_at: string | null }[]>([]);
  const [passkeyMsg, setPasskeyMsg] = useState<string | null>(null);

  const refresh = useCallback(async (t: string) => {
    setProfile(await getProfile(t));
    setWatchlist(await getWatchlist(t));
    setNotifications(await getNotifications(t));
    listPasskeys()
      .then(setPasskeys)
      .catch(() => undefined);
  }, []);

  useEffect(() => setTokenState(getToken()), []);
  useEffect(() => {
    if (token) void refresh(token).catch(() => setError("Session expired"));
  }, [token, refresh]);
  useEffect(() => {
    void getQuiz()
      .then(setQuestions)
      .catch(() => undefined);
  }, []);

  async function authenticate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const t = mode === "login" ? await login(email, password) : await signup(email, password);
      setTokenState(t);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed");
    }
  }

  if (!token) {
    return (
      <main className="mx-auto flex max-w-md flex-col gap-4 px-6 py-12">
        <h1 className="text-2xl font-bold text-slate-900">Your trust profile</h1>
        <form className="flex flex-col gap-3" onSubmit={authenticate}>
          <input className={input} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className={input} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
          <button className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">{mode === "signup" ? "Create account" : "Sign in"}</button>
        </form>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button className="text-sm text-slate-500 underline" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
          {mode === "signup" ? "Already have an account? Sign in" : "Need an account? Sign up"}
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-5 px-6 py-12">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Your trust profile</h1>
        <button
          className="text-sm text-slate-500 underline"
          onClick={() => {
            setToken(null);
            setTokenState(null);
          }}
        >
          Sign out
        </button>
      </div>

      {profile && (
        <div className={card}>
          <div className="flex items-center justify-between">
            <p className="font-semibold text-slate-800">{profile.display_name ?? profile.email}</p>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${TIER_STYLES[profile.tier] ?? ""}`}>{profile.tier}</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">Reputation</p>
              <p className="text-xl font-bold text-slate-900">{profile.reputation_score}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">Identity trust</p>
              <p className="text-xl font-bold text-slate-900">{profile.identity_trust}</p>
            </div>
          </div>
          {profile.badges.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {profile.badges.map((b) => (
                <span key={`${b.badge}-${b.scope}`} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                  {b.badge.replaceAll("_", " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className={card}>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold text-slate-800">Passkey (MFA)</p>
            <p className="text-xs text-slate-500">Admin accounts must have one enrolled (ADR-020).</p>
          </div>
          <button
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={async () => {
              setPasskeyMsg(null);
              try {
                await enrollPasskey();
                setPasskeyMsg("Passkey enrolled.");
                setPasskeys(await listPasskeys());
              } catch (err) {
                setPasskeyMsg(err instanceof ApiError ? err.message : "Enrollment failed");
              }
            }}
          >
            {passkeys.length > 0 ? "Add another" : "Enroll passkey"}
          </button>
        </div>
        {passkeys.length > 0 ? (
          <ul className="mt-3 space-y-1 text-xs text-slate-600">
            {passkeys.map((p) => (
              <li key={p.credential_id} className="flex justify-between gap-3">
                <span className="truncate font-mono">{p.credential_id.slice(0, 20)}…</span>
                <span>{p.created_at ? p.created_at.slice(0, 10) : ""}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-amber-600">No passkey yet.</p>
        )}
        {passkeyMsg && <p className="mt-2 text-xs text-slate-500">{passkeyMsg}</p>}
      </div>

      {profile && !profile.phone_verified && (
        <div className={card}>
          <p className="font-semibold text-slate-800">Become a Verified Reporter</p>
          <p className="mt-1 text-xs text-slate-500">Verify your phone to earn the Verified Reporter badge (+30 identity trust).</p>
          <div className="mt-3 flex flex-col gap-2">
            <input className={input} placeholder="Phone (+62...)" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <button
              className="rounded-lg border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700"
              onClick={async () => {
                const r = await verifyPhoneStart(token, phone || "+620000000000");
                setDevCode(r.dev_code ?? "(sent)");
              }}
            >
              Send code
            </button>
            {devCode && <p className="text-xs text-amber-600">Dev code: {devCode}</p>}
            {devCode && (
              <>
                <input className={input} placeholder="Enter code" value={code} onChange={(e) => setCode(e.target.value)} />
                <button
                  className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white"
                  onClick={async () => {
                    await verifyPhoneConfirm(token, code);
                    await refresh(token);
                    setDevCode(null);
                  }}
                >
                  Confirm
                </button>
              </>
            )}
          </div>
        </div>
      )}

      <div className={card}>
        <div className="flex items-center justify-between">
          <p className="font-semibold text-slate-800">Notifications</p>
          {profile && (profile.unread_notifications ?? 0) > 0 && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">{profile.unread_notifications} unread</span>
          )}
        </div>
        {notifications.length === 0 ? (
          <p className="mt-1 text-xs text-slate-500">Alerts about accounts you watch and reports you file appear here.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {notifications.slice(0, 10).map((n) => (
              <li
                key={n.id}
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
                  n.read_at ? "bg-slate-100 text-slate-500" : "bg-blue-50 text-slate-800"
                }`}
              >
                <span>{n.type.replaceAll("_", " ").toLowerCase()}</span>
                {!n.read_at && (
                  <button
                    className="text-xs text-blue-700 underline"
                    onClick={async () => {
                      await markNotificationRead(token, n.id);
                      await refresh(token);
                    }}
                  >
                    Mark read
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={card}>
        <p className="font-semibold text-slate-800">Watchlist</p>
        {watchlist.length === 0 ? (
          <p className="mt-1 text-xs text-slate-500">Watch accounts from the check page to get alerts when new reports arrive.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {watchlist.map((w) => (
              <li key={w.entity_id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <span className="font-mono text-slate-800">{w.account_masked}</span>
                <span className="text-xs text-slate-500">{w.risk_level}</span>
                <button
                  className="text-xs text-rose-600 underline"
                  onClick={async () => {
                    await removeWatch(token, w.entity_id);
                    await refresh(token);
                  }}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={card}>
        <p className="font-semibold text-slate-800">Scam Vaccine</p>
        <p className="mt-1 text-xs text-slate-500">Answer 3 scenarios to earn the Anti-Scam Aware badge.</p>
        <div className="mt-3 space-y-4">
          {questions.map((q, qi) => (
            <div key={q.id}>
              <p className="text-sm text-slate-700">{q.scenario}</p>
              <div className="mt-1 space-y-1">
                {q.options.map((opt, oi) => (
                  <label key={oi} className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="radio"
                      name={q.id}
                      checked={answers[qi] === oi}
                      onChange={() => {
                        const next = [...answers];
                        next[qi] = oi;
                        setAnswers(next);
                      }}
                    />
                    {opt}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button
            className="rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white"
            onClick={async () => {
              const r = await submitQuiz(token, answers);
              setQuizResult(r.passed ? "Passed — badge granted!" : `Scored ${r.correct}/3 — try again`);
              await refresh(token);
            }}
          >
            Submit answers
          </button>
          {quizResult && <p className="text-sm text-slate-700">{quizResult}</p>}
        </div>
      </div>

      <div className={card}>
        <p className="font-semibold text-slate-800">Privacy &amp; your data</p>
        <p className="mt-1 text-xs text-slate-500">Export everything we hold about you, or erase your reports and votes.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="rounded-lg border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700"
            onClick={async () => {
              const data = await exportData(token);
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "trustpay-export.json";
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Export my data
          </button>
          <button
            className="rounded-lg border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-600"
            onClick={async () => {
              if (!window.confirm("Erase your reports, votes, flags and watchlist? This cannot be undone.")) return;
              await eraseData(token);
              await refresh(token);
              window.alert("Your data has been erased.");
            }}
          >
            Erase my data
          </button>
        </div>
      </div>
    </main>
  );
}
