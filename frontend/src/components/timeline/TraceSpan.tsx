"use client";

import { useState } from "react";
import type { TimelineSpan, SpanKind } from "@/lib/types";
import { LatencyBadge } from "./LatencyBadge";

const KIND_STYLES: Record<SpanKind, { dot: string; label: string; border: string }> = {
  CHAIN:   { dot: "bg-indigo-500",  label: "text-indigo-300  bg-indigo-500/10  border-indigo-500/30",  border: "border-indigo-500/20" },
  TOOL:    { dot: "bg-sky-500",     label: "text-sky-300     bg-sky-500/10     border-sky-500/30",     border: "border-sky-500/20" },
  LLM:     { dot: "bg-violet-500",  label: "text-violet-300  bg-violet-500/10  border-violet-500/30",  border: "border-violet-500/20" },
  EVAL:    { dot: "bg-emerald-500", label: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30", border: "border-emerald-500/20" },
  REFLECT: { dot: "bg-amber-500",   label: "text-amber-300   bg-amber-500/10   border-amber-500/30",   border: "border-amber-500/20" },
};

const STATUS_DOT: Record<string, string> = {
  ok:      "bg-emerald-500",
  error:   "bg-red-500 animate-pulse",
  pending: "bg-amber-500 animate-pulse",
};

interface Props {
  span: TimelineSpan;
  depth?: number;
}

export function TraceSpan({ span, depth = 0 }: Props) {
  const [open, setOpen] = useState(depth === 0);
  const style = KIND_STYLES[span.kind];
  const hasChildren = span.children && span.children.length > 0;

  return (
    <div className={`${depth > 0 ? "ml-5 border-l border-gray-800 pl-3" : ""}`}>
      <div
        className={`flex items-start gap-2 py-2 px-3 rounded-lg border ${style.border} bg-gray-900/60 mb-1 cursor-pointer hover:bg-gray-900 transition-colors`}
        onClick={() => hasChildren && setOpen(!open)}
        role={hasChildren ? "button" : undefined}
        aria-expanded={hasChildren ? open : undefined}
      >
        {/* Status dot */}
        <span className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 ${STATUS_DOT[span.status]}`} />

        {/* Kind badge */}
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border flex-shrink-0 ${style.label}`}>
          {span.kind}
        </span>

        {/* Name */}
        <span className="text-sm text-gray-200 font-mono flex-1 truncate">{span.name}</span>

        {/* Latency */}
        <LatencyBadge ms={span.latency_ms} />

        {/* Expand toggle */}
        {hasChildren && (
          <span className="text-gray-600 text-xs ml-1">{open ? "▾" : "▸"}</span>
        )}
      </div>

      {/* Attributes */}
      {open && span.attributes && Object.keys(span.attributes).length > 0 && (
        <div className={`ml-5 mb-1 px-3 py-2 rounded border border-gray-800 bg-gray-950/60 text-[11px] font-mono text-gray-400 grid grid-cols-2 gap-x-4 gap-y-0.5`}>
          {Object.entries(span.attributes).map(([k, v]) => (
            <div key={k} className="flex gap-1 col-span-1 truncate">
              <span className="text-gray-600">{k}:</span>
              <span className="text-gray-300 truncate">{String(v)}</span>
            </div>
          ))}
          {span.trace_id && (
            <div className="col-span-2 flex gap-1 mt-1 pt-1 border-t border-gray-800">
              <span className="text-gray-600">trace_id:</span>
              <span className="text-indigo-400 truncate">{span.trace_id}</span>
            </div>
          )}
        </div>
      )}

      {/* Children */}
      {open && hasChildren && span.children!.map((child, idx) => (
        <TraceSpan key={`${child.id}-${idx}`} span={child} depth={depth + 1} />
      ))}
    </div>
  );
}
