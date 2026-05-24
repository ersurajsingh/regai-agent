"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import type {
  TimelineData,
  ComplianceIssue,
  EvaluationResult,
  ReflectionResult,
  TraceAwareAnalysis,
} from "@/lib/types";
import { TraceSpan } from "./timeline/TraceSpan";
import { EvalScoreBar } from "./timeline/EvalScoreBar";
import { RiskBadge } from "./timeline/RiskBadge";
import { ReflectionPanel } from "./timeline/ReflectionPanel";

type Tab = "spans" | "analysis" | "evaluation" | "reflection" | "trace-aware" | "gemini-reasoning";

const TABS: { id: Tab; label: string }[] = [
  { id: "spans",       label: "Trace Spans" },
  { id: "analysis",    label: "Analysis" },
  { id: "evaluation",  label: "Evaluation" },
  { id: "reflection",  label: "Reflection" },
  { id: "trace-aware", label: "Trace-Aware" },
  { id: "gemini-reasoning", label: "Gemini Reasoning" },
];

interface Props {
  data: TimelineData;
}

export default function ObservabilityTimeline({ data }: Props) {
  const [tab, setTab] = useState<Tab>("spans");

  return (
    <div className="w-full rounded-xl border border-gray-800 bg-gray-950 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/80">
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-sm font-semibold text-gray-200">Observability Timeline</span>
          <span className="text-xs text-gray-600 font-mono truncate max-w-[200px]">
            {data.upload_id}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-gray-500">
          <span>{data.spans.length} spans</span>
          {data.analysis && (
            <RiskBadge level={data.analysis.risk_level} />
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800 bg-gray-900/40 overflow-x-auto">
        {TABS.map((t) => {
          const hasData =
            t.id === "spans"       ? data.spans.length > 0 :
            t.id === "analysis"    ? !!data.analysis :
            t.id === "evaluation"  ? !!data.evaluation :
            t.id === "reflection"  ? !!data.reflection :
            !!data.trace_aware;

          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-xs font-medium whitespace-nowrap transition-colors border-b-2 ${
                tab === t.id
                  ? "border-indigo-500 text-indigo-300"
                  : "border-transparent text-gray-500 hover:text-gray-300"
              } ${!hasData ? "opacity-40 cursor-not-allowed" : ""}`}
              disabled={!hasData}
            >
              {t.label}
              {!hasData && <span className="ml-1 text-[9px]">—</span>}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="p-4 overflow-y-auto max-h-[600px]">
        {tab === "spans" && (
          <div className="space-y-1">
            {data.spans.length === 0 ? (
              <Empty message="No spans yet. Run an analysis to see trace data." />
            ) : (
              data.spans.map((span) => <TraceSpan key={span.id} span={span} />)
            )}
          </div>
        )}

        {tab === "analysis" && data.analysis && (
  <AnalysisPanel analysis={data.analysis} />
)}

{tab === "evaluation" && data.evaluation && (
  <EvaluationPanel evaluation={data.evaluation} />
)}

{tab === "reflection" && data.reflection && (
  <ReflectionPanel reflection={data.reflection} />
)}

{tab === "trace-aware" && data.trace_aware && (
  <TraceAwarePanel ta={data.trace_aware} />
)}

{tab === "gemini-reasoning" && data.analysis && (
  <GeminiReasoningPanel analysis={data.analysis} />
)}
      </div>
    </div>
  );
}

// ── Sub-panels ─────────────────────────────────────────────────────────────────

function AnalysisPanel({ analysis }: { analysis: NonNullable<TimelineData["analysis"]> }) {
  return (
    <div className="space-y-4">
      {/* Risk summary */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Risk Level">
          <RiskBadge level={analysis.risk_level} />
        </StatCard>
        <StatCard label="Risk Score">
          <span className="text-2xl font-bold text-gray-100">{analysis.risk_score}</span>
          <span className="text-xs text-gray-500">/100</span>
        </StatCard>
      </div>

      {/* Trace ID */}
      {analysis.trace_id && (
        <div className="rounded-lg border border-gray-800 bg-gray-900/60 px-3 py-2 flex items-center gap-2">
          <span className="text-[10px] text-gray-500 uppercase tracking-wide">Phoenix Trace ID</span>
          <span className="text-xs font-mono text-indigo-400 truncate">{analysis.trace_id}</span>
        </div>
      )}

      {/* Explanation */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
        <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Explanation</p>
        <p className="text-xs text-gray-300 leading-relaxed">{analysis.explanation}</p>
      </div>

      {/* Issues */}
      {analysis.issues.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-2">
            Issues ({analysis.issues.length})
          </p>
          <div className="space-y-2">
            {analysis.issues.map((issue, i) => (
              <IssueRow key={i} issue={issue} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {analysis.recommendations.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-2">
            Recommendations
          </p>
          <div className="space-y-2">
            {analysis.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="flex-shrink-0 h-5 w-5 rounded-full bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-[10px] font-bold">
                  {rec.priority}
                </span>
                <div>
                  <p className="text-gray-200 font-medium">{rec.action}</p>
                  <p className="text-gray-500 mt-0.5">{rec.rationale}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EvaluationPanel({ evaluation }: { evaluation: EvaluationResult }) {
  const dims = [
    evaluation.decision_quality,
    evaluation.reasoning_quality,
    evaluation.hallucination_risk,
    evaluation.rule_alignment,
  ];

  return (
    <div className="space-y-4">
      {/* Overall */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Overall Score">
          <span className="text-2xl font-bold text-gray-100">
            {Math.round(evaluation.overall_score * 100)}%
          </span>
        </StatCard>
        <StatCard label="Verdict">
          <LabelBadge label={evaluation.overall_label} />
        </StatCard>
      </div>

      {/* Dimension bars */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4 space-y-3">
        {dims.map((d) => (
          <EvalScoreBar
            key={d.name}
            name={d.name}
            score={d.score}
            label={d.label as any}
            explanation={d.explanation}
          />
        ))}
      </div>

      {/* Rule comparison */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
        <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-2">Rule Engine Comparison</p>
        <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
          <div>
            <p className="text-gray-500 text-[10px]">Precision</p>
            <p className="text-gray-200 font-bold">{(evaluation.rule_comparison.precision * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-gray-500 text-[10px]">Recall</p>
            <p className="text-gray-200 font-bold">{(evaluation.rule_comparison.recall * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-gray-500 text-[10px]">F1</p>
            <p className="text-gray-200 font-bold">{(evaluation.rule_comparison.f1_score * 100).toFixed(0)}%</p>
          </div>
        </div>
        {evaluation.rule_comparison.extra_issues.length > 0 && (
          <p className="text-[11px] text-red-400">
            ⚠ Unsupported by rules: {evaluation.rule_comparison.extra_issues.join(", ")}
          </p>
        )}
        {evaluation.rule_comparison.missed_issues.length > 0 && (
          <p className="text-[11px] text-amber-400">
            ↓ Missed: {evaluation.rule_comparison.missed_issues.join(", ")}
          </p>
        )}
      </div>

      {/* Summary */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
        <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">Evaluation Summary</p>
        <p className="text-xs text-gray-300 leading-relaxed">{evaluation.evaluation_summary}</p>
      </div>
    </div>
  );
}

function TraceAwarePanel({ ta }: { ta: TraceAwareAnalysis }) {
  return (
    <div className="space-y-4">
      {/* Meta */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Prior Analyses">
          <span className="text-2xl font-bold text-gray-100">{ta.prior_analyses_used}</span>
        </StatCard>
        <StatCard label="Session Trend">
          <TrendBadge trend={ta.session_trend} />
        </StatCard>
        <StatCard label="Mistakes Avoided">
          <span className="text-2xl font-bold text-emerald-400">{ta.repeated_mistakes_avoided.length}</span>
        </StatCard>
      </div>

      {/* History summary */}
      {ta.history_summary && (
        <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-3">
          <p className="text-[10px] text-indigo-400 uppercase tracking-wide mb-1">What the agent learned</p>
          <p className="text-xs text-gray-300 leading-relaxed">{ta.history_summary}</p>
        </div>
      )}

      {/* Historical patterns */}
      {ta.historical_patterns.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-2">Historical Patterns</p>
          <div className="space-y-2">
            {ta.historical_patterns.map((p, i) => (
              <div key={i} className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-xs">
                <span className="text-[10px] font-bold text-gray-500 uppercase">{p.pattern_type.replace(/_/g, " ")}</span>
                <p className="text-gray-300 mt-1">{p.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reasoning changes */}
      {ta.reasoning_changes.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-2">
            Reasoning Changes ({ta.reasoning_changes.length})
          </p>
          <div className="space-y-2">
            {ta.reasoning_changes.map((rc, i) => (
              <div key={i} className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-xs space-y-1">
                <p className="text-gray-400 font-medium capitalize">{rc.dimension.replace(/_/g, " ")}</p>
                <div className="flex items-center gap-2">
                  <span className="text-red-400 line-through">{rc.previous_value}</span>
                  <span className="text-gray-600">→</span>
                  <span className="text-emerald-400">{rc.current_value}</span>
                </div>
                <p className="text-gray-500 italic">{rc.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Shared atoms ───────────────────────────────────────────────────────────────

function IssueRow({ issue }: { issue: ComplianceIssue }) {
  const SEV_COLOR: Record<string, string> = {
    critical: "border-red-500/40 bg-red-500/5",
    high:     "border-orange-500/40 bg-orange-500/5",
    medium:   "border-amber-500/40 bg-amber-500/5",
    low:      "border-gray-700 bg-gray-900/40",
  };
  return (
    <div className={`rounded-lg border p-3 text-xs ${SEV_COLOR[issue.severity] ?? SEV_COLOR.low}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="font-semibold text-gray-200 capitalize">{issue.category.replace(/_/g, " ")}</span>
        <span className="text-gray-500">·</span>
        <span className="text-gray-400 uppercase text-[10px]">{issue.severity}</span>
        {issue.regulation && (
          <span className="ml-auto text-[10px] text-indigo-400 truncate max-w-[160px]">{issue.regulation}</span>
        )}
      </div>
      <p className="text-gray-400 leading-relaxed">{issue.description}</p>
    </div>
  );
}

function StatCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-center">
      <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <div className="flex items-center justify-center gap-1">{children}</div>
    </div>
  );
}

function LabelBadge({ label }: { label: string }) {
  const COLOR: Record<string, string> = {
    excellent: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    good:      "text-sky-300     bg-sky-500/10     border-sky-500/30",
    fair:      "text-amber-300   bg-amber-500/10   border-amber-500/30",
    poor:      "text-red-300     bg-red-500/10     border-red-500/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-semibold capitalize ${COLOR[label] ?? "text-gray-400 bg-gray-800 border-gray-700"}`}>
      {label}
    </span>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  const MAP: Record<string, { icon: string; color: string }> = {
    improving:          { icon: "↑", color: "text-emerald-400" },
    degrading:          { icon: "↓", color: "text-red-400" },
    stable:             { icon: "→", color: "text-sky-400" },
    insufficient_data:  { icon: "—", color: "text-gray-500" },
  };
  const { icon, color } = MAP[trend] ?? MAP.insufficient_data;
  return (
    <span className={`text-lg font-bold ${color}`}>{icon} <span className="text-xs capitalize">{trend.replace(/_/g, " ")}</span></span>
  );
}

function Empty({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-600">
      <span className="text-3xl mb-2">◎</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}

function GeminiReasoningPanel({ analysis }: { analysis: NonNullable<TimelineData["analysis"]> }) {
  return (
    <div className="space-y-4">
      {/* Gemini Prompt */}
      {analysis.gemini_prompt && (
        <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">
            Gemini Prompt
          </p>
          <p className="text-xs text-gray-300 break-all whitespace-pre-wrap">{analysis.gemini_prompt}</p>
        </div>
      )}

      {/* Gemini Raw Response */}
      {analysis.gemini_raw_response && (
        <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">
            Gemini Raw Response
          </p>
          <p className="text-xs text-gray-300 break-all whitespace-pre-wrap">{analysis.gemini_raw_response}</p>
        </div>
      )}

      {/* Fallback if no Gemini data */}
      {!analysis.gemini_prompt && !analysis.gemini_raw_response && (
        <div className="text-center py-8 text-gray-500">
          <p>No Gemini reasoning data available for this analysis.</p>
        </div>
      )}
    </div>
  );
}
