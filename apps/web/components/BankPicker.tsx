"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Bank } from "@/lib/api";

/** Searchable institution picker. Value is `${country}:${code}` so codes that
 *  repeat across countries stay unambiguous; the country is derived from the
 *  chosen bank (no separate country step). */
export function BankPicker({
  banks,
  value,
  onChange,
  placeholder = "Search bank / e-wallet…",
  inputClassName,
}: {
  banks: Bank[];
  value: string;
  onChange: (bank: Bank) => void;
  placeholder?: string;
  inputClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(
    () => banks.find((b) => `${b.country}:${b.code}` === value) ?? null,
    [banks, value],
  );

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? banks.filter((b) =>
          `${b.name} ${b.short_name ?? ""} ${b.code} ${b.country}`.toLowerCase().includes(q),
        )
      : banks;
    return list.slice(0, 80);
  }, [banks, query]);

  const cls =
    inputClassName ??
    "w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-100";

  return (
    <div ref={boxRef} className="relative">
      <input
        className={cls}
        value={open ? query : selected ? `${selected.name} (${selected.country})` : ""}
        placeholder={placeholder}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        role="combobox"
        aria-expanded={open}
        aria-controls="bankpicker-listbox"
        autoComplete="off"
      />
      {open && (
        <div
          id="bankpicker-listbox"
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          {filtered.length === 0 ? (
            <p className="px-3 py-2 text-xs text-slate-400">No match</p>
          ) : (
            filtered.map((b) => {
              const key = `${b.country}:${b.code}`;
              const active = key === value;
              return (
                <button
                  key={key}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange(b);
                    setOpen(false);
                    setQuery("");
                  }}
                  className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-blue-50 ${
                    active ? "bg-blue-50 font-semibold text-blue-800" : "text-slate-700"
                  }`}
                >
                  <span className="truncate">{b.name}</span>
                  <span className="shrink-0 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                    {b.country}
                    {b.bank_type === "E_WALLET" ? " · e-wallet" : ""}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
