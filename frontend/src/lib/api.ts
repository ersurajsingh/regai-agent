import axios from "axios";
import type {
  ComplianceAnalysis,
  EvaluationResult,
  ReflectionResult,
  TraceAwareAnalysis,
  TimelineData,
  TimelineSpan,
} from "./types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
});

export async function createSession(): Promise<{ session_id: string; token: string }> {
  const { data } = await api.post("/sessions/");
  return data;
}

export async function sendQuery(
  sessionId: string,
  query: string
): Promise<{ answer: string; trace_id: string }> {
  const { data } = await api.post("/query/", { session_id: sessionId, query });
  return data;
}

export async function uploadDocument(
  sessionId: string,
  file: File
): Promise<{ document_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/documents/upload?session_id=${sessionId}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function uploadTransactions(
  sessionId: string,
  file: File
): Promise<{ upload_id: string; row_count: number; columns: string[] }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/transactions/upload?session_id=${sessionId}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function runCompliance(
  sessionId: string,
  uploadId: string
): Promise<ComplianceAnalysis> {
  const { data } = await api.post("/compliance/analyze", {
    session_id: sessionId,
    upload_id: uploadId,
  });
  return data;
}

export async function runEvaluation(
  sessionId: string,
  uploadId: string,
  analysisTraceId?: string
): Promise<EvaluationResult> {
  const { data } = await api.post("/compliance/evaluate", {
    session_id: sessionId,
    upload_id: uploadId,
    analysis_trace_id: analysisTraceId ?? null,
  });
  return data;
}

export async function runReflection(
  sessionId: string,
  uploadId: string
): Promise<ReflectionResult> {
  const { data } = await api.post("/compliance/reflect", {
    session_id: sessionId,
    upload_id: uploadId,
  });
  return data;
}

export async function runTraceAware(
  sessionId: string,
  uploadId: string
): Promise<TraceAwareAnalysis> {
  const { data } = await api.post("/compliance/analyze/trace-aware", {
    session_id: sessionId,
    upload_id: uploadId,
  });
  return data;
}

// ── Timeline builder ───────────────────────────────────────────────────────────
// Assembles a TimelineData object from individual API results.
// In production this would be a single backend endpoint; for the hackathon
// we compose it client-side from the existing endpoints.

export function buildTimeline(
  sessionId: string,
  uploadId: string,
  analysis: ComplianceAnalysis | null,
  evaluation: EvaluationResult | null,
  reflection: ReflectionResult | null,
  traceAware: TraceAwareAnalysis | null,
  analysisLatencyMs?: number,
  evaluationLatencyMs?: number,
  reflectionLatencyMs?: number,
  traceAwareLatencyMs?: number
): TimelineData {
  const spans: TimelineSpan[] = [];

  if (analysis) {
    const analysisSpan: TimelineSpan = {
      id: analysis.trace_id ?? "analysis",
      name: "compliance_analysis_workflow",
      kind: "CHAIN",
      status: "ok",
      trace_id: analysis.trace_id,
      latency_ms: analysisLatencyMs,
      attributes: {
        risk_level: analysis.risk_level,
        risk_score: analysis.risk_score,
        issue_count: analysis.issues.length,
      },
      children: [
        { id: "kyc", name: "detect_missing_kyc", kind: "TOOL", status: "ok",
          attributes: { issues: analysis.issues.filter(i => i.category === "missing_kyc").length } },
        { id: "dup", name: "detect_duplicate_invoices", kind: "TOOL", status: "ok",
          attributes: { issues: analysis.issues.filter(i => i.category === "duplicate_invoice").length } },
        { id: "aml", name: "detect_aml_patterns", kind: "TOOL", status: "ok",
          attributes: { issues: analysis.issues.filter(i => i.category === "aml").length } },
        { id: "sus", name: "detect_suspicious_activity", kind: "TOOL", status: "ok",
          attributes: { issues: analysis.issues.filter(i => i.category === "suspicious_activity").length } },
        { id: "llm", name: "gemini.generate_content", kind: "LLM", status: "ok",
          attributes: { model: "gemini-2.0-flash" } },
      ],
    };
    spans.push(analysisSpan);
  }

  if (evaluation) {
    spans.push({
      id: evaluation.evaluation_id,
      name: "evaluation_workflow",
      kind: "EVAL",
      status: "ok",
      trace_id: evaluation.evaluation_trace_id,
      latency_ms: evaluationLatencyMs,
      attributes: {
        overall_score: evaluation.overall_score,
        overall_label: evaluation.overall_label,
        f1_score: evaluation.rule_comparison.f1_score,
      },
    });
  }

  if (reflection) {
    spans.push({
      id: reflection.reflection_id,
      name: "reflection_workflow",
      kind: "REFLECT",
      status: "ok",
      trace_id: reflection.reflection_trace_id,
      latency_ms: reflectionLatencyMs,
      attributes: {
        false_positive_count: reflection.false_positive_assessments.length,
        risk_score_delta: reflection.delta.risk_score_delta,
        risk_level_changed: reflection.delta.risk_level_changed,
      },
    });
  }

  if (traceAware) {
    spans.push({
      id: traceAware.trace_id ?? "trace-aware",
      name: "trace_aware_workflow",
      kind: "CHAIN",
      status: "ok",
      trace_id: traceAware.trace_id,
      latency_ms: traceAwareLatencyMs,
      attributes: {
        prior_analyses_used: traceAware.prior_analyses_used,
        session_trend: traceAware.session_trend,
        reasoning_changes: traceAware.reasoning_changes.length,
      },
    });
  }

  return { session_id: sessionId, upload_id: uploadId, analysis, evaluation, reflection, trace_aware: traceAware, spans };
}
