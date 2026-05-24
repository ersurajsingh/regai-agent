// ── Compliance ─────────────────────────────────────────────────────────────────

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type IssueSeverity = "low" | "medium" | "high" | "critical";
export type EvalLabel = "excellent" | "good" | "fair" | "poor" | "n/a";

export interface ComplianceIssue {
  category: string;
  severity: IssueSeverity;
  row_indices: number[];
  description: string;
  regulation: string | null;
  evidence: Record<string, unknown>;
}

export interface ComplianceRecommendation {
  priority: number;
  action: string;
  rationale: string;
}

export interface ComplianceAnalysis {
  trace_id: string | null;
  upload_id: string;
  session_id: string;
  risk_level: RiskLevel;
  risk_score: number;
  issues: ComplianceIssue[];
  recommendations: ComplianceRecommendation[];
  explanation: string;
  gemini_prompt?: string | null;
  gemini_raw_response?: string | null;
  created_at?: string;
}

// ── Evaluation ─────────────────────────────────────────────────────────────────

export interface EvalDimension {
  name: string;
  label: EvalLabel;
  score: number;
  explanation: string;
}

export interface RuleComparison {
  rule_issue_count: number;
  llm_issue_count: number;
  missed_issues: string[];
  extra_issues: string[];
  confirmed_issues: string[];
  precision: number;
  recall: number;
  f1_score: number;
}

export interface EvaluationResult {
  evaluation_id: string;
  session_id: string;
  upload_id: string;
  analysis_trace_id: string | null;
  decision_quality: EvalDimension;
  reasoning_quality: EvalDimension;
  hallucination_risk: EvalDimension;
  rule_alignment: EvalDimension;
  overall_score: number;
  overall_label: EvalLabel;
  rule_comparison: RuleComparison;
  evaluation_summary: string;
  evaluation_trace_id: string | null;
  created_at?: string;
}

// ── Reflection ─────────────────────────────────────────────────────────────────

export interface ReasoningChange {
  dimension: string;
  previous_value: string;
  current_value: string;
  reason: string;
}

export interface ReflectionResult {
  reflection_id: string;
  session_id: string;
  upload_id: string;
  original_trace_id: string | null;
  false_positive_assessments: Array<{
    issue_index: number;
    original_description: string;
    verdict: string;
    reasoning: string;
    confidence: number;
  }>;
  reasoning_critiques: Array<{
    aspect: string;
    critique: string;
    severity: string;
  }>;
  critique_summary: string;
  improved_risk_level: RiskLevel;
  improved_risk_score: number;
  improved_explanation: string;
  delta: {
    risk_level_changed: boolean;
    original_risk_level: string;
    improved_risk_level: string;
    risk_score_delta: number;
    issues_added: ComplianceIssue[];
    issues_removed_indices: number[];
    recommendations_changed: boolean;
  };
  reflection_trace_id: string | null;
  created_at?: string;
}

// ── Trace-aware ────────────────────────────────────────────────────────────────

export interface HistoricalPattern {
  pattern_type: string;
  description: string;
  affected_categories: string[];
  evidence: Record<string, unknown>;
}

export interface TraceAwareAnalysis extends ComplianceAnalysis {
  historical_patterns: HistoricalPattern[];
  reasoning_changes: ReasoningChange[];
  history_summary: string;
  prior_analyses_used: number;
  session_trend: string;
  repeated_mistakes_avoided: string[];
}

// ── Timeline ───────────────────────────────────────────────────────────────────

export type SpanKind = "CHAIN" | "TOOL" | "LLM" | "EVAL" | "REFLECT";

export interface TimelineSpan {
  id: string;
  name: string;
  kind: SpanKind;
  status: "ok" | "error" | "pending";
  latency_ms?: number;
  trace_id?: string | null;
  attributes?: Record<string, string | number | boolean>;
  children?: TimelineSpan[];
  started_at?: string;
}

export interface TimelineData {
  session_id: string;
  upload_id: string;
  analysis: ComplianceAnalysis | null;
  evaluation: EvaluationResult | null;
  reflection: ReflectionResult | null;
  trace_aware: TraceAwareAnalysis | null;
  spans: TimelineSpan[];
}
