import type { EvalLabel } from "@/lib/types";

const LABEL_COLOR: Record<EvalLabel, string> = {
  excellent: "text-emerald-400",
  good:      "text-sky-400",
  fair:      "text-amber-400",
  poor:      "text-red-400",
  "n/a":     "text-gray-500",
};

const BAR_COLOR: Record<EvalLabel, string> = {
  excellent: "bg-emerald-500",
  good:      "bg-sky-500",
  fair:      "bg-amber-500",
  poor:      "bg-red-500",
  "n/a":     "bg-gray-600",
};

interface Props {
  name: string;
  score: number;
  label: EvalLabel;
  explanation?: string;
}

export function EvalScoreBar({ name, score, label, explanation }: Props) {
  const pct = Math.round(score * 100);
  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-400 capitalize">{name.replace(/_/g, " ")}</span>
        <span className={`text-xs font-semibold ${LABEL_COLOR[label]}`}>
          {pct}% · {label}
        </span>
      </div>
      <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${BAR_COLOR[label]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {explanation && (
        <p className="mt-1 text-[11px] text-gray-500 hidden group-hover:block leading-relaxed">
          {explanation}
        </p>
      )}
    </div>
  );
}
