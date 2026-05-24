import type { ReactNode } from "react";
import type { ReflectionResult } from "@/lib/types";
import { RiskBadge } from "./RiskBadge";

export function ReflectionPanel({ reflection }: { reflection: ReflectionResult }) {
  const { delta } = reflection;
  const deltaSign = delta.risk_score_delta > 0 ? "+" : "";
  const deltaColor = delta.risk_score_delta < 0 ? "text-emerald-400" : delta.risk_score_delta > 0 ? "text-red-400" : "text-gray-400";

  return (
    <div className="space-y-4">
      {/* Delta summary */}
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Original risk" value={<RiskBadge level={delta.original_risk_level as any} />} />
        <Stat label="Improved risk" value={<RiskBadge level={delta.improved_risk_level as any} />} />
        <Stat
          label="Score delta"
          value={<span className={`text-sm font-bold ${deltaColor}`}>{deltaSign}{delta.risk_score_delta}</span>}
        />
      </div>

      {/* Critique summary */}
      {reflection.critique_summary && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
          <p className="text-xs text-amber-300 font-semibold mb-1">Critique Summary</p>
          <p className="text-xs text-gray-300 leading-relaxed">{reflection.critique_summary}</p>
        </div>
      )}

      {/* False positives */}
      {reflection.false_positive_assessments.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide mb-2">
            False Positive Assessments ({reflection.false_positive_assessments.length})
          </p>
          <div className="space-y-1.5">
            {reflection.false_positive_assessments.map((fp, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className={`mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold border flex-shrink-0 ${
                  fp.verdict === "likely_false_positive"
                    ? "bg-red-500/10 text-red-300 border-red-500/30"
                    : fp.verdict === "confirmed"
                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                    : "bg-gray-700 text-gray-400 border-gray-600"
                }`}>
                  {fp.verdict.replace(/_/g, " ")}
                </span>
                <span className="text-gray-400 leading-relaxed">{fp.original_description}</span>
                <span className="text-gray-600 flex-shrink-0">{Math.round(fp.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reasoning critiques */}
      {reflection.reasoning_critiques.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide mb-2">
            Reasoning Critiques
          </p>
          <div className="space-y-1.5">
            {reflection.reasoning_critiques.map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className={`mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold border flex-shrink-0 ${
                  c.severity === "significant" ? "bg-red-500/10 text-red-300 border-red-500/30"
                  : c.severity === "moderate" ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                  : "bg-gray-700 text-gray-400 border-gray-600"
                }`}>
                  {c.severity}
                </span>
                <div>
                  <span className="text-gray-300 font-medium">{c.aspect}: </span>
                  <span className="text-gray-400">{c.critique}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-center">
      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <div className="flex justify-center">{value}</div>
    </div>
  );
}
