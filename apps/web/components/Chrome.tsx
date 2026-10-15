"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { EmergencyBar } from "./EmergencyBar";
import { Navbar } from "./Navbar";
import { Footer } from "./Footer";

/** Standard public chrome. The analyst console (/admin) renders its own shell. */
export function Chrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const bare = pathname.startsWith("/admin");

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-800 antialiased">
      {!bare && (
        <>
          <EmergencyBar />
          <Navbar />
        </>
      )}
      <div className="flex flex-1 flex-col">{children}</div>
      {!bare && <Footer />}
    </div>
  );
}
