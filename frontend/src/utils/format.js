export function formatKpiValue(value, unit = "") {
  if (value == null || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const rounded = abs >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded.toLocaleString("en-IN")}${unit ? ` ${unit}` : ""}`.trim();
}

export function formatCompact(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

// Compact axis tick: keeps large ₹/count axes narrow so left/right axis labels
// never collide with the plot or the legend. Small values keep one decimal.
export function formatAxisTick(value) {
  if (value == null || Number.isNaN(value)) return "";
  const abs = Math.abs(value);
  if (abs >= 1000) {
    return new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(value);
  }
  if (abs >= 100 || Number.isInteger(value)) return String(Math.round(value));
  return String(Math.round(value * 10) / 10);
}

export function progressColor(pct) {
  if (pct == null) return "bg-base-600";
  if (pct >= 90) return "bg-positive";
  if (pct >= 60) return "bg-orange-500";
  return "bg-negative";
}

export function trendColor(trend) {
  if (trend === "up") return "text-positive";
  if (trend === "down") return "text-negative";
  return "text-base-400";
}

export function formatDateTime(isoString) {
  if (!isoString) return "";
  try {
    return new Date(isoString).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return isoString;
  }
}

export function csvEscape(value) {
  const str = String(value ?? "");
  if (/[",\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

export function downloadCsv(filename, rows) {
  const csv = rows.map((row) => row.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
