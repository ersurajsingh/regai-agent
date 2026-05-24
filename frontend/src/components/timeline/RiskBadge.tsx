import type { RiskLevel } from "@/lib/types";

const COLORS: Record<RiskLevel, string> = {
  low:      "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  medium:   "bg-amber-500/20  text-amber-300  border-amber-500/40",
  high:     "bg-orange-500/20 text-orange-300 border-orange-500/40",
  critical: "bg-red-500/20    text-red-300    border-red-500/40",
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold uppercase tracking-wide ${COLORS[level]}`}>
      {level}
    </span>
  );
}
