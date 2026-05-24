export function LatencyBadge({ ms }: { ms?: number }) {
  if (ms === undefined) return null;
  const color = ms < 500 ? "text-emerald-400" : ms < 2000 ? "text-amber-400" : "text-red-400";
  const label = ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  return (
    <span className={`text-[11px] font-mono ${color}`}>{label}</span>
  );
}
