export default function RiskRadarLegend() {
  return (
    <div className="flex items-center gap-4 rounded-lg bg-white px-3 py-2 text-xs text-slate-600 shadow-sm border border-slate-100">
      <span className="font-semibold text-ink">Risk radar:</span>
      <span className="flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-full bg-[#16A34A]" /> Low
      </span>
      <span className="flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-full bg-[#F2A65A]" /> Moderate
      </span>
      <span className="flex items-center gap-1">
        <span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" /> High
      </span>
    </div>
  );
}
