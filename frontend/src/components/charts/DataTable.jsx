export default function DataTable({ kpi, points }) {
  const shape = kpi.data_shape;

  if (shape === "category_compare") {
    const breakdown = points[0]?.breakdown || {};
    const categories = Object.keys(breakdown);
    const subkeys = Object.keys(breakdown[categories[0]] || {});
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-base-700 text-base-400">
              <th className="py-2 pr-4 font-medium">{kpi.breakdown_label || "Category"}</th>
              {subkeys.map((k) => (
                <th key={k} className="py-2 pr-4 font-medium capitalize">
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((c) => (
              <tr key={c} className="border-b border-base-800 text-base-200">
                <td className="py-2 pr-4">{c}</td>
                {subkeys.map((k) => (
                  <td key={k} className="py-2 pr-4">
                    {breakdown[c][k]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (shape === "time_breakdown") {
    const keys = Object.keys(points[0]?.breakdown || {});
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-base-700 text-base-400">
              <th className="py-2 pr-4 font-medium">Period</th>
              {keys.map((k) => (
                <th key={k} className="py-2 pr-4 font-medium">
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.period_label} className="border-b border-base-800 text-base-200">
                <td className="py-2 pr-4">{p.period_label}</td>
                {keys.map((k) => (
                  <td key={k} className="py-2 pr-4">
                    {p.breakdown?.[k]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // time_line / time_dual: primary + (optional) secondary + target + revision
  const hasSecondary = !!kpi.secondary_label && points.some((p) => p.secondary_value != null);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-base-700 text-base-400">
            <th className="py-2 pr-4 font-medium">Period</th>
            <th className="py-2 pr-4 font-medium">
              {kpi.display_title || kpi.name}
              {kpi.unit ? ` (${kpi.unit})` : ""}
            </th>
            {hasSecondary && (
              <th className="py-2 pr-4 font-medium">
                {kpi.secondary_label}
                {kpi.secondary_unit ? ` (${kpi.secondary_unit})` : ""}
              </th>
            )}
            <th className="py-2 pr-4 font-medium">Target</th>
            <th className="py-2 pr-4 font-medium">Data status</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.period_label} className="border-b border-base-800 text-base-200">
              <td className="py-2 pr-4">{p.period_label}</td>
              <td className="py-2 pr-4">{p.value ?? "—"}</td>
              {hasSecondary && <td className="py-2 pr-4 text-base-400">{p.secondary_value ?? "—"}</td>}
              <td className="py-2 pr-4 text-base-400">{p.target_value ?? "—"}</td>
              <td className="py-2 pr-4 text-xs text-base-500">{p.revision || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
