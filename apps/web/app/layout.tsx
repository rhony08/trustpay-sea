import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Chrome } from "@/components/Chrome";

export const metadata: Metadata = {
  title: "TrustPay SEA — Payment Risk & Reputation Registry",
  description:
    "Community-driven payment-risk & reputation registry for Southeast Asia — check who you are paying before you transfer.",
  manifest: "/manifest.webmanifest",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-800 antialiased">
        <Chrome>{children}</Chrome>
      </body>
    </html>
  );
}
