import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Chrome } from "@/components/Chrome";
import { LocaleProvider } from "@/components/LocaleProvider";

export const metadata: Metadata = {
  title: "TrustPay SEA — Payment Risk & Reputation Registry",
  description:
    "Community-driven payment-risk & reputation registry for Southeast Asia — check who you are paying before you transfer.",
  manifest: "/manifest.webmanifest",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-slate-50 text-slate-800 antialiased">
        <LocaleProvider>
          <Chrome>{children}</Chrome>
        </LocaleProvider>
      </body>
    </html>
  );
}
