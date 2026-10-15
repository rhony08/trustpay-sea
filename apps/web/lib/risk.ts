/** Shared risk-band model (NG-2 polarity clarity, Doc 12 §2). Styles only —
 *  human-readable labels come from i18n keys. */

export type RiskBandKey = "LOW" | "CAUTION" | "HIGH" | "CRITICAL";

export interface RiskBand {
  key: RiskBandKey;
  /** i18n key for the band label. */
  labelKey: string;
  /** Tailwind classes for the score number. */
  scoreText: string;
  /** Tailwind classes for the segmented gauge fill. */
  gaugeFill: string;
  /** Solid segment colour classes for the 4-band track. */
  segment: string;
  /** Badge (pill) classes: bg/text/border. */
  badge: string;
}

const BANDS: Record<RiskBandKey, RiskBand> = {
  LOW: {
    key: "LOW",
    labelKey: "risk.low",
    scoreText: "text-emerald-600",
    gaugeFill: "w-1/4 bg-emerald-500",
    segment: "bg-emerald-500",
    badge: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  CAUTION: {
    key: "CAUTION",
    labelKey: "risk.caution",
    scoreText: "text-amber-600",
    gaugeFill: "w-2/4 bg-amber-400",
    segment: "bg-amber-400",
    badge: "border-amber-200 bg-amber-50 text-amber-800",
  },
  HIGH: {
    key: "HIGH",
    labelKey: "risk.high",
    scoreText: "text-orange-600",
    gaugeFill: "w-3/4 bg-orange-500",
    segment: "bg-orange-500",
    badge: "border-orange-200 bg-orange-50 text-orange-800",
  },
  CRITICAL: {
    key: "CRITICAL",
    labelKey: "risk.critical",
    scoreText: "text-red-600",
    gaugeFill: "w-full bg-red-600",
    segment: "bg-red-600",
    badge: "border-red-200 bg-red-50 text-red-800",
  },
};

export function riskBand(score: number): RiskBand {
  if (score >= 80) return BANDS.CRITICAL;
  if (score >= 51) return BANDS.HIGH;
  if (score >= 21) return BANDS.CAUTION;
  return BANDS.LOW;
}

/** Map server risk_level labels onto normalised band keys. */
export function bandFromLevel(level: string): RiskBandKey {
  switch (level) {
    case "CRITICAL_FRAUD":
      return "CRITICAL";
    case "HIGH_RISK":
      return "HIGH";
    case "CAUTION":
      return "CAUTION";
    default:
      return "LOW";
  }
}

/** i18n key for a server risk-level string. */
export function levelKey(level: string): string {
  return `level.${level}`;
}

/** i18n key for a report category enum value. */
export function categoryKey(value: string): string {
  return `cat.${value}`;
}
