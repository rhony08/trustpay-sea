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
  in_registry: true;
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
