"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  addWatch,
  eraseData,
  exportData,
  getNotifications,
  getProfile,
  getQuiz,
  getToken,
  getWatchlist,
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
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100 outline-none focus:border-emerald-400";

const TIER_STYLES: Record<string, string> = {
  NEWCOMER: "border-slate-600 text-slate-300",
  CONTRIBUTOR: "border-sky-500/40 text-sky-300",
  TRUSTED: "border-emerald-500/40 text-emerald-300",
  GUARDIAN: "border-amber-500/40 text-amber-300",
};

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

  const refresh = useCallback(async (t: string) => {
    setProfile(await getProfile(t));
    setWatchlist(await getWatchlist(t));
    setNotifications(await getNotifications(t));
  }, []);

  useEffect(() => setTokenState(getToken()), []);
  useEffect(() => {
    if (token) void refresh(token).catch(() => setError("Session expired"));
  }, [token, refresh]);
  useEffect(() => {
    void getQuiz().then(setQuestions).catch(() => undefined);
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
      <main className="mx-auto flex min-h-screen max-w-md flex-col gap-4 px-6 py-12">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← TrustPay SEA
        </Link>
        <h1 className="text-2xl font-bold">Your trust profile</h1>
        <form className="flex flex-col gap-3" onSubmit={authenticate}>
          <input className={input} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className={input} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
          <button className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950">
            {mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>
        {error && <p className="text-sm text-rose-300">{error}</p>}
        <button className="text-sm text-slate-400 underline" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
          {mode === "signup" ? "Already have an account? Sign in" : "Need an account? Sign up"}
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-5 px-6 py-12">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← TrustPay SEA
        </Link>
        <button
          className="text-sm text-slate-400 underline"
          onClick={() => {
            setToken(null);
            setTokenState(null);
          }}
        >
          Sign out
        </button>
      </div>
      <h1 className="text-2xl font-bold">Your trust profile</h1>

      {profile && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
          <div className="flex items-center justify-between">
            <p className="font-semibold">{profile.display_name ?? profile.email}</p>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${TIER_STYLES[profile.tier] ?? ""}`}>
              {profile.tier}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg bg-slate-800/60 p-3">
              <p className="text-xs text-slate-400">Reputation</p>
              <p className="text-xl font-bold">{profile.reputation_score}</p>
            </div>
            <div className="rounded-lg bg-slate-800/60 p-3">
              <p className="text-xs text-slate-400">Identity trust</p>
              <p className="text-xl font-bold">{profile.identity_trust}</p>
            </div>
          </div>
          {profile.badges.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {profile.badges.map((b) => (
                <span key={`${b.badge}-${b.scope}`} className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs text-amber-200">
                  {b.badge.replaceAll("_", " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {profile && !profile.phone_verified && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
          <p className="font-semibold">Become a Verified Reporter</p>
          <p className="mt-1 text-xs text-slate-400">
            Verify your phone to earn the Verified Reporter badge (+30 identity trust).
          </p>
          <div className="mt-3 flex flex-col gap-2">
            <input className={input} placeholder="Phone (+62...)" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <button
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm"
              onClick={async () => {
                const r = await verifyPhoneStart(token, phone || "+620000000000");
                setDevCode(r.dev_code ?? "(sent)");
              }}
            >
              Send code
            </button>
            {devCode && <p className="text-xs text-amber-300">Dev code: {devCode}</p>}
            {devCode && (
              <>
                <input className={input} placeholder="Enter code" value={code} onChange={(e) => setCode(e.target.value)} />
                <button
                  className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950"
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

      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <div className="flex items-center justify-between">
          <p className="font-semibold">Notifications</p>
          {profile && (profile.unread_notifications ?? 0) > 0 && (
            <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300">
              {profile.unread_notifications} unread
            </span>
          )}
        </div>
        {notifications.length === 0 ? (
          <p className="mt-1 text-xs text-slate-400">
            Alerts about accounts you watch and reports you file appear here.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {notifications.slice(0, 10).map((n) => (
              <li
                key={n.id}
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
                  n.read_at ? "bg-slate-800/40 text-slate-400" : "bg-slate-800/70 text-slate-100"
                }`}
              >
                <span>{n.type.replaceAll("_", " ").toLowerCase()}</span>
                {!n.read_at && (
                  <button
                    className="text-xs text-emerald-300 underline"
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

      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <p className="font-semibold">Watchlist</p>
        {watchlist.length === 0 ? (
          <p className="mt-1 text-xs text-slate-400">
            Watch accounts from the check page to get alerts when new reports arrive.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {watchlist.map((w) => (
              <li key={w.entity_id} className="flex items-center justify-between rounded-lg bg-slate-800/60 px-3 py-2 text-sm">
                <span className="font-mono">{w.account_masked}</span>
                <span className="text-xs text-slate-400">{w.risk_level}</span>
                <button
                  className="text-xs text-rose-300 underline"
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

      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <p className="font-semibold">Scam Vaccine</p>
        <p className="mt-1 text-xs text-slate-400">
          Answer 3 scenarios to earn the Anti-Scam Aware badge.
        </p>
        <div className="mt-3 space-y-4">
          {questions.map((q, qi) => (
            <div key={q.id}>
              <p className="text-sm text-slate-200">{q.scenario}</p>
              <div className="mt-1 space-y-1">
                {q.options.map((opt, oi) => (
                  <label key={oi} className="flex items-center gap-2 text-sm text-slate-300">
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
            className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950"
            onClick={async () => {
              const r = await submitQuiz(token, answers);
              setQuizResult(r.passed ? "Passed — badge granted!" : `Scored ${r.correct}/3 — try again`);
              await refresh(token);
            }}
          >
            Submit answers
          </button>
          {quizResult && <p className="text-sm text-slate-300">{quizResult}</p>}
        </div>
      </div>

      <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5">
        <p className="font-semibold">Privacy &amp; your data</p>
        <p className="mt-1 text-xs text-slate-400">
          Export everything we hold about you, or erase your reports and votes.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm"
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
            className="rounded-lg border border-rose-500/50 px-4 py-2 text-sm text-rose-300"
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
