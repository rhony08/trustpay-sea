import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * PWA Share Target (3B.6): accept a shared QR screenshot / text, decode it
 * server-side, then hand the payload to /check to screen in one tap.
 */
export async function POST(req: NextRequest) {
  const form = await req.formData();
  const file = form.get("image");
  const text = (form.get("text") as string | null) ?? "";
  let payload = text;

  if (file instanceof File && file.size > 0) {
    const out = new FormData();
    out.append("file", file);
    try {
      const resp = await fetch(`${API}/api/v1/qr/decode`, { method: "POST", body: out });
      if (resp.ok) {
        const body = await resp.json();
        payload = body?.data?.qr_payload ?? payload;
      }
    } catch {
      // fall through — redirect to /check so the user can paste manually
    }
  }

  const url = new URL("/check", req.url);
  if (payload) url.searchParams.set("qr", payload);
  return NextResponse.redirect(url, 303);
}
