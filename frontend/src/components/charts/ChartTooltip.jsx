export default function ChartTooltip({ active, payload, label, unitMap = {} }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-base-700 bg-base-850 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 font-semibold text-white">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="flex items-center gap-1.5" style={{ color: entry.color }}>
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-base-300">{entry.name}:</span>
          <span className="font-medium">
            {typeof entry.value === "number" ? entry.value.toLocaleString("en-IN", { maximumFractionDigits: 1 }) : entry.value}
            {unitMap[entry.dataKey] ? ` ${unitMap[entry.dataKey]}` : ""}
          </span>
        </p>
      ))}
    </div>
  );
}
