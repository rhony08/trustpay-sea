/** Typed client for the resolver API (Phase 1). */

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HolderDisclosure {
  name: string;
  label: string;
  confidence: "VERIFIED" | "UNVERIFIED";
}

export interface EntityProfile {
  entity: {
    id: string;
    entity_type: string;
    scheme: string | null;
    country: string;
    institution: string | null;
    account_masked: string;
    merchant_name: string | null;
    merchant_city: string | null;
    mcc: string | null;
    nmid: string | null;
    holder: HolderDisclosure | null;
  };
  risk_assessment: {
    risk_score: number;
    risk_level: string;
    verification_status: string;
    badge: { color: string; label: string };
    is_gov_blacklisted: boolean;
    is_under_dispute: boolean;
    is_verified_legit: boolean;
  };
  community_signals: {
    total_reports: number;
    admin_verified_reports: number;
    report_velocity_7d: number;
    total_loss_by_currency: Record<string, number>;
  };
  reports?: ReportView[];
  ai_summary?: { text: string; cached: boolean; grounded: boolean } | null;
  related_fact_checks?: FactCheck[] | null;
  search_intelligence?: SearchIntelligence | null;
  in_registry: true;
}

export interface SearchIntelligence {
  total_searches: number | null;
  total_searches_display: string | null;
  searches_7d: number;
  searches_30d: number;
  last_searched_at: string | null;
  threshold_gated: boolean;
}

export interface FactCheck {
  text: string | null;
  claimant: string | null;
  rating: string | null;
  url: string | null;
}

export interface ReportEvidence {
  media_type: string;
  media_url: string | null;
  is_blurred_pii: boolean;
  ai_tampering_detected: boolean;
}

export interface ReportView {
  id: string;
  payment_entity_id: string;
  category: string;
  severity: number;
  currency: string;
  loss_amount: number | null;
  incident_date: string | null;
  description: string | null;
  processing_status: "PROCESSING" | "PUBLISHED" | "FAILED";
  admin_verification_status: string;
  status: string;
  ai_risk_score: number | null;
  ai_tampering_detected: boolean;
  evidence: ReportEvidence[];
  created_at: string | null;
}

export interface Bank {
  country: string;
  code: string;
  name: string;
  short_name: string | null;
  bank_type: string;
  bic: string | null;
  national_id: string | null;
}


export interface QrMetadata {
  scheme: string;
  point_of_initiation: string;
  merchant_name: string | null;
  merchant_city: string | null;
  national_merchant_id: string | null;
  mcc: string | null;
  currency: string | null;
  amount: string | null;
  country: string | null;
  homoglyph_warning: boolean;
  normalized_merchant_name?: string | null;
  qr_changed_since_last_seen?: boolean;
}

export type ScreenResult =
  | { status: "success"; data: EntityProfile & { qr_metadata?: QrMetadata; query: unknown } }
  | {
      status: "not_found";
      data: {
        in_registry: false;
        message: string;
        query: unknown;
        qr_metadata?: QrMetadata;
      };
    };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API}${path}`, init);
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new ApiError(resp.status, body?.detail ?? `HTTP ${resp.status}`);
  }
  return body as T;
}

export function screenAccount(params: {
  country: string;
  bank: string;
  account: string;
}): Promise<ScreenResult> {
  const qs = new URLSearchParams(params).toString();
  return request<ScreenResult>(`/api/v1/entities/account?${qs}`);
}

export function screenQr(qr_payload: string): Promise<ScreenResult> {
  return request<ScreenResult>(`/api/v1/entities/qr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_payload }),
  });
}

export async function decodeQrImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const body = await request<{ status: string; data: { qr_payload: string; detail?: string } }>(
    `/api/v1/qr/decode`,
    { method: "POST", body: form },
  );
  if (body.status !== "success") {
    throw new ApiError(400, body.data.detail ?? "QR decoded but not an EMVCo payment code");
  }
  return body.data.qr_payload;
}

/** Mirror of services/api/app/resolver/banks.py — MVP duplication, unify later. */
export const BANKS: Record<string, { code: string; name: string }[]> = {
  ID: [
    { code: "014", name: "BCA" },
    { code: "002", name: "BRI" },
    { code: "008", name: "Mandiri" },
    { code: "009", name: "BNI" },
    { code: "022", name: "CIMB Niaga" },
    { code: "011", name: "Bank Danamon" },
    { code: "013", name: "Permata Bank" },
    { code: "451", name: "BSI" },
    { code: "GOPAY", name: "GoPay (e-wallet)" },
    { code: "OVO", name: "OVO (e-wallet)" },
    { code: "DANA", name: "DANA (e-wallet)" },
  ],
  MY: [
    { code: "MBB", name: "Maybank" },
    { code: "CIMB", name: "CIMB Bank" },
    { code: "PBB", name: "Public Bank" },
    { code: "RHB", name: "RHB Bank" },
  ],
  TH: [
    { code: "KBANK", name: "Kasikorn (KBank)" },
    { code: "SCB", name: "SCB" },
    { code: "BBL", name: "Bangkok Bank" },
    { code: "KTB", name: "Krungthai" },
  ],
  SG: [
    { code: "DBS", name: "DBS" },
    { code: "OCBC", name: "OCBC" },
    { code: "UOB", name: "UOB" },
  ],
  VN: [
    { code: "VCB", name: "Vietcombank" },
    { code: "MB", name: "MB Bank" },
    { code: "BIDV", name: "BIDV" },
  ],
  PH: [
    { code: "BDO", name: "BDO" },
    { code: "BPI", name: "BPI" },
    { code: "MB", name: "Metrobank" },
  ],
};

export const COUNTRIES = [
  { code: "ID", label: "Indonesia" },
  { code: "MY", label: "Malaysia" },
  { code: "TH", label: "Thailand" },
  { code: "SG", label: "Singapore" },
  { code: "VN", label: "Vietnam" },
  { code: "PH", label: "Philippines" },
];

export const REPORT_CATEGORIES = [
  { value: "ONLINE_SHOP_GHOSTING", label: "Online shop ghosting" },
  { value: "FAKE_JOB", label: "Fake job" },
  { value: "INVESTMENT_PIG_BUTCHERING", label: "Investment / pig butchering" },
  { value: "PHISHING_PRETEXTING", label: "Phishing / pretexting" },
  { value: "IMPERSONATION", label: "Impersonation" },
  { value: "UNAUTHORIZED_LENDING_PINJOL", label: "Unauthorized lending / pinjol" },
  { value: "NO_DELIVERY_GOODS", label: "No delivery of goods" },
  { value: "EVENT_TICKET_FRAUD", label: "Event ticket fraud" },
  { value: "OTHER", label: "Other" },
];

const TOKEN_KEY = "trustpay_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export interface CreateReportInput {
  target:
    | { kind: "ACCOUNT"; country: string; bank: string; account: string }
    | { kind: "QR"; qr_payload: string };
  category: string;
  severity: number;
  description: string;
  currency?: string;
  loss_amount?: number | null;
  incident_date?: string | null;
  consent: boolean;
}

export async function signup(email: string, password: string, displayName?: string): Promise<string> {
  const body = await request<{ access_token: string }>("/api/v1/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  setToken(body.access_token);
  return body.access_token;
}

export async function login(email: string, password: string): Promise<string> {
  const body = await request<{ access_token: string }>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  setToken(body.access_token);
  return body.access_token;
}

export async function listBanks(country: string): Promise<Bank[]> {
  const body = await request<{ data: { banks: Bank[] } }>(
    `/api/v1/banks?country=${country}`,
  );
  return body.data.banks;
}

async function authed<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = { ...(init.headers ?? {}), Authorization: `Bearer ${token}` };
  return request<T>(path, { ...init, headers });
}

export async function createReport(
  token: string,
  input: CreateReportInput,
): Promise<{ report_id: string; processing_status: string; entity_masked: string }> {
  const body = await authed<{
    data: { report_id: string; processing_status: string; entity_masked: string };
  }>("/api/v1/reports", token, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(input),
  });
  return body.data;
}

export async function uploadEvidence(token: string, reportId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  form.append("media_type", "TRANSFER_SLIP");
  await authed(`/api/v1/reports/${reportId}/evidence`, token, { method: "POST", body: form });
}

export async function getReport(reportId: string): Promise<ReportView> {
  const body = await request<{ data: ReportView }>(`/api/v1/reports/${reportId}`);
  return body.data;
}

