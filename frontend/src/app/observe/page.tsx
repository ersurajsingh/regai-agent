"use client";

import { useState, useCallback } from "react";
import ObservabilityTimeline from "@/components/ObservabilityTimeline";
import {
  createSession,
  uploadTransactions,
  runCompliance,
  runEvaluation,
  runReflection,
  runTraceAware,
  buildTimeline,
} from "@/lib/api";
import type {
  TimelineData,
  ComplianceAnalysis,
  EvaluationResult,
  ReflectionResult,
  TraceAwareAnalysis,
} from "@/lib/types";

type Step =
  | "idle"
  | "uploading"
  | "analyzing"
  | "evaluating"
  | "reflecting"
  | "trace-aware"
  | "done"
  | "error";

const STEP_LABELS: Record<Step, string> = {
  idle:         "Ready",
  uploading:    "Uploading CSV…",
  analyzing:    "Running compliance analysis…",
  evaluating:   "Evaluating output quality…",
  reflecting:   "Running self-reflection…",
  "trace-aware":"Running trace-aware analysis…",
  done:         "Complete",
  error:        "Error",
};

export default function ObservePage() {
  const [step, setStep] = useState<Step>("idle");
  const [error, setError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);

  // Partial results accumulated as pipeline runs
  const [analysis, setAnalysis] = useState<ComplianceAnalysis | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [reflection, setReflection] = useState<ReflectionResult | null>(null);
  const [traceAware, setTraceAware] = useState<TraceAwareAnalysis | null>(null);

   const refreshTimeline = useCallback(
   (
     sid: string, uid: string,
     a: ComplianceAnalysis | null,
     e: EvaluationResult | null,
     r: ReflectionResult | null,
     ta: TraceAwareAnalysis | null,
     analysisLatencyMs: number | undefined = undefined,
     evaluationLatencyMs: number | undefined = undefined,
     reflectionLatencyMs: number | undefined = undefined,
     traceAwareLatencyMs: number | undefined = undefined,
   ) => {
     setTimeline(buildTimeline(sid, uid, a, e, r, ta, analysisLatencyMs, evaluationLatencyMs, reflectionLatencyMs, traceAwareLatencyMs));
   },
   []
 );

   const handleFile = useCallback(async (file: File) => {
     setError(null);
     setStep("uploading");

     try {
       // 1. Session
       const session = await createSession();
       const sid = session.session_id;
       setSessionId(sid);

       // 2. Upload CSV
       const upload = await uploadTransactions(sid, file);
       const uid = upload.upload_id;
       setUploadId(uid);

       // 3. Compliance analysis
       setStep("analyzing");
       const startAnalysis = performance.now();
       const a = await runCompliance(sid, uid);
       const analysisLatencyMs = performance.now() - startAnalysis;
       setAnalysis(a);
       refreshTimeline(sid, uid, a, null, null, null, analysisLatencyMs, undefined, undefined, undefined);

       // 4. Evaluation
       setStep("evaluating");
       const startEvaluation = performance.now();
       const e = await runEvaluation(sid, uid, a.trace_id ?? undefined);
       const evaluationLatencyMs = performance.now() - startEvaluation;
       setEvaluation(e);
       refreshTimeline(sid, uid, a, e, null, null, analysisLatencyMs, evaluationLatencyMs, undefined, undefined);

       // 5. Reflection
       setStep("reflecting");
       const startReflection = performance.now();
       const r = await runReflection(sid, uid);
       const reflectionLatencyMs = performance.now() - startReflection;
       setReflection(r);
       refreshTimeline(sid, uid, a, e, r, null, analysisLatencyMs, evaluationLatencyMs, reflectionLatencyMs, undefined);

       // 6. Trace-aware (uses the reflection + evaluation as prior context)
       setStep("trace-aware");
       const startTraceAware = performance.now();
       const ta = await runTraceAware(sid, uid);
       const traceAwareLatencyMs = performance.now() - startTraceAware;
       setTraceAware(ta);
       refreshTimeline(sid, uid, a, e, r, ta, analysisLatencyMs, evaluationLatencyMs, reflectionLatencyMs, traceAwareLatencyMs);

       setStep("done");
     } catch (err: unknown) {
       const msg = err instanceof Error ? err.message : "Pipeline failed.";
       setError(msg);
       setStep("error");
     }
   }, [refreshTimeline]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const isRunning = !["idle", "done", "error"].includes(step);

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-6">
      {/* Page header */}
      <div className="max-w-5xl mx-auto mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-100">RegAI Observability</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Gemini reasoning · Phoenix traces · Evaluation · Self-reflection
            </p>
          </div>
          <a href="/" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
            ← Chat
          </a>
        </div>
      </div>

      <div className="max-w-5xl mx-auto space-y-4">
        {/* Upload zone */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
            isRunning
              ? "border-indigo-500/40 bg-indigo-500/5"
              : "border-gray-700 hover:border-gray-600 bg-gray-900/40 cursor-pointer"
          }`}
        >
          {isRunning ? (
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
              <p className="text-sm text-indigo-300 font-medium">{STEP_LABELS[step]}</p>
              <PipelineProgress step={step} />
            </div>
          ) : (
            <label className="cursor-pointer">
              <input
                type="file"
                accept=".csv"
                className="sr-only"
                onChange={handleChange}
                disabled={isRunning}
              />
              <div className="flex flex-col items-center gap-2">
                <span className="text-3xl">📊</span>
                <p className="text-sm text-gray-300 font-medium">
                  Drop a transaction CSV or click to upload
                </p>
                <p className="text-xs text-gray-600">
                  Required columns: transaction_id, amount, vendor, timestamp, customer_name, kyc_status
                </p>
                {step === "done" && (
                  <p className="text-xs text-emerald-400 mt-1">✓ Pipeline complete — upload another file to re-run</p>
                )}
              </div>
            </label>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Session / upload IDs */}
        {(sessionId || uploadId) && (
          <div className="flex gap-4 text-[11px] font-mono text-gray-600">
            {sessionId && <span>session: <span className="text-gray-500">{sessionId}</span></span>}
            {uploadId  && <span>upload:  <span className="text-gray-500">{uploadId}</span></span>}
          </div>
        )}

        {/* Timeline */}
        {timeline && <ObservabilityTimeline data={timeline} />}
      </div>
    </main>
  );
}

// ── Pipeline progress indicator ────────────────────────────────────────────────

const PIPELINE_STEPS: { id: Step; label: string }[] = [
  { id: "uploading",    label: "Upload" },
  { id: "analyzing",   label: "Analyze" },
  { id: "evaluating",  label: "Evaluate" },
  { id: "reflecting",  label: "Reflect" },
  { id: "trace-aware", label: "Trace-Aware" },
];

const STEP_ORDER: Step[] = ["uploading", "analyzing", "evaluating", "reflecting", "trace-aware", "done"];

function PipelineProgress({ step }: { step: Step }) {
  const currentIdx = STEP_ORDER.indexOf(step);
  return (
    <div className="flex items-center gap-1 mt-1">
      {PIPELINE_STEPS.map((s, i) => {
        const sIdx = STEP_ORDER.indexOf(s.id);
        const done = sIdx < currentIdx;
        const active = sIdx === currentIdx;
        return (
          <div key={s.id} className="flex items-center gap-1">
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
              done   ? "bg-emerald-500/20 text-emerald-400" :
              active ? "bg-indigo-500/20 text-indigo-300" :
                       "bg-gray-800 text-gray-600"
            }`}>
              {done ? "✓" : active ? "●" : "○"} {s.label}
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <span className={`text-[10px] ${done ? "text-emerald-600" : "text-gray-700"}`}>→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
