import { useMemo, useRef, useState } from "react";
import { useKpiHistory } from "../../hooks/useKpiHistory";
import { useEvents } from "../../hooks/useEvents";
import { downloadCsv, formatKpiValue } from "../../utils/format";
import { exportChartAsPng } from "../../utils/exportChart";
import { ChartSkeleton } from "../Skeletons";
import ErrorBanner from "../ErrorBanner";
import ChartRenderer, { PALETTE, mergeEventsByPeriod } from "./ChartRenderer";
import DataTable from "./DataTable";
import KpiProvenance from "../KpiProvenance";

const RANGES = [
  { value: "5y", label: "Last 5 Years" },
  { value: "10y", label: "Last 10 Years" },
  { value: "full", label: "Full History (since 2014)" },
];

function yearToPeriodLabel(year) {
  return `FY${String(year + 1).slice(-2)}`;
}

// Target / aspiration numbers, shown as short text near the chart. Replaces the
// old on-chart SVG line labels and the card-header readout - one quiet source of
// the numbers, no clutter. Time-series charts get a compact tag tucked into the
// emptiest plot corner (`targetTagPlacement`); full-bleed shapes (stacked area,
// category bars) have no empty corner, so they get a right-aligned caption just
// above the plot instead.
const TAG_POS = {
  // `top-9` drops the tag below the event-badge row that pins to the plot top
  // (badges compress toward the corners on narrow screens); the `bottom` offsets
  // clear the x-axis ticks (and the range brush, when the chart shows one).
  "top-right": "top-9 right-2 items-end text-right",
  "top-left": "top-9 left-[62px] items-start text-left",
  "bottom-right": "right-2 items-end text-right",
  "bottom-left": "left-[62px] items-start text-left",
};

// Keep the numbers genuinely short: collapse any "% of …" unit to just "%", and
// drop anything longer - the card header + Y axis already carry the full unit.
function shortUnit(unit) {
  if (!unit) return "";
  if (/%/.test(unit)) return "%";
  return unit.length > 10 ? "" : unit;
}

function TargetBits({ official, asp, u }) {
  return (
    <>
      {official != null && (
        <span className="text-base-400">
          Target <span className="font-medium text-base-300">{formatKpiValue(official, u)}</span>
        </span>
      )}
      {asp != null && asp !== official && (
        <span className="text-positive/90">
          Aspiration <span className="font-medium">{formatKpiValue(asp, u)}</span>
        </span>
      )}
    </>
  );
}

function ChartTargetTag({ kpi, unit, placement, hasBrush }) {
  const official = kpi.target_value || null;
  const asp = kpi.aspirational_target ?? null;
  if (official == null && asp == null) return null;
  const u = shortUnit(unit);

  if (placement === "banner") {
    return (
      <div className="mb-1 flex flex-wrap justify-end gap-x-3 gap-y-0.5 px-1 text-[10px] leading-tight">
        <TargetBits official={official} asp={asp} u={u} />
      </div>
    );
  }

  const pos = TAG_POS[placement] || TAG_POS["top-right"];
  const bottomOffset = placement.startsWith("bottom") ? (hasBrush ? "bottom-[70px]" : "bottom-10") : "";
  return (
    <div
      className={`pointer-events-none absolute z-10 flex max-w-[46%] flex-col gap-0.5 rounded-md border border-base-700/50 bg-base-900/85 px-2 py-1 text-[10px] leading-tight backdrop-blur-sm ${pos} ${bottomOffset}`}
    >
      <TargetBits official={official} asp={asp} u={u} />
    </div>
  );
}

// Pick the plot corner the data line stays furthest out of. The line is
// normalised to x 0..1 / y 0..1 (target + aspiration folded into the domain,
// since their reference lines render with `extendDomain`), then each of the four
// corner boxes is scored by the smallest gap between the line and the box over
// that box's x-span. Highest gap wins; ties break top-right → top-left →
// bottom-right → bottom-left. Series without a scalar `value` (breakdowns,
// category compares) have no clear corner, so they use the "banner" slot.
const TAG_CORNERS = [
  { key: "top-right", xr: [0.58, 0.99], edge: 0.72, top: true },
  { key: "top-left", xr: [0.03, 0.42], edge: 0.72, top: true },
  { key: "bottom-right", xr: [0.58, 0.99], edge: 0.3, top: false },
  { key: "bottom-left", xr: [0.03, 0.42], edge: 0.3, top: false },
];

function targetTagPlacement(points, kpi) {
  // Only a plain single line (time_line) reliably leaves an empty corner. Dual
  // axes, breakdowns and category bars fill the plot or carry a legend - those
  // get the right-aligned caption above the plot instead.
  if (kpi.data_shape !== "time_line") return "banner";
  const vals = points.map((p) => p?.value).filter((v) => v != null);
  if (vals.length < 3) return "banner";
  const extra = [kpi.target_value || null, kpi.aspirational_target ?? null].filter((v) => v != null);
  const min = Math.min(...vals, ...extra);
  const max = Math.max(...vals, ...extra);
  const range = max - min || 1;
  const n = vals.length;

  // Walk the line densely (interpolating between vertices) so a steep segment
  // that cuts through a corner box is caught, not just the data points.
  const line = [];
  for (let i = 0; i < n - 1; i++) {
    const y0 = (vals[i] - min) / range;
    const y1 = (vals[i + 1] - min) / range;
    for (let s = 0; s < 6; s++) {
      const t = s / 6;
      line.push({ x: (i + t) / (n - 1), y: y0 + (y1 - y0) * t });
    }
  }
  line.push({ x: 1, y: (vals[n - 1] - min) / range });

  let best = null;
  for (const c of TAG_CORNERS) {
    let gap = Infinity;
    for (const p of line) {
      if (p.x < c.xr[0] || p.x > c.xr[1]) continue;
      gap = Math.min(gap, c.top ? c.edge - p.y : p.y - c.edge);
    }
    if (gap === Infinity) gap = 1;
    if (!best || gap > best.gap + 0.001) best = { key: c.key, gap };
  }
  // No corner with real breathing room -> use the caption above the plot.
  return best.gap > 0.06 ? best.key : "banner";
}

function Toggle({ active, onClick, children, title }) {
  return (
    <button
      title={title}
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
        active
          ? "border-cyan-500/50 bg-cyan-500/15 text-cyan-400"
          : "border-base-700 bg-base-800 text-base-400 hover:text-base-200"
      }`}
    >
      {children}
    </button>
  );
}

export default function ChartCard({ kpi, ministryCode, hero = false }) {
  const [range, setRange] = useState("full");
  const [growthMode, setGrowthMode] = useState(false);
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [peerCompare, setPeerCompare] = useState(false);
  const [tableView, setTableView] = useState(false);
  const [hiddenKeys, setHiddenKeys] = useState(() => new Set());
  const chartRef = useRef(null);

  const { data: rawPoints, isLoading, isError, error, refetch } = useKpiHistory(kpi.id, range);
  const { data: allEvents } = useEvents(ministryCode);

  const canGrowth = kpi.data_shape === "time_line";
  const canPeer = ["time_line", "time_dual", "time_breakdown"].includes(kpi.data_shape);
  const canBreakdownFilter = kpi.data_shape === "time_breakdown";

  const { points, unit, secondaryUnit } = useMemo(() => {
    if (!rawPoints?.length) return { points: [], unit: kpi.unit, secondaryUnit: kpi.secondary_unit };

    if (growthMode && canGrowth) {
      const transformed = rawPoints.map((p, i) => {
        const prev = rawPoints[i - 1];
        const value = i === 0 || prev?.value == null || p.value == null || prev.value === 0 ? null : Math.round(((p.value - prev.value) / Math.abs(prev.value)) * 1000) / 10;
        return { ...p, value, target_value: null };
      });
      return { points: transformed, unit: "% YoY change", secondaryUnit: kpi.secondary_unit };
    }

    return { points: rawPoints, unit: kpi.unit, secondaryUnit: kpi.secondary_unit };
  }, [rawPoints, growthMode, canGrowth, kpi.unit, kpi.secondary_unit]);

  const breakdownKeys = useMemo(() => Object.keys(points[0]?.breakdown || {}), [points]);
  const visibleKeys = useMemo(
    () => (canBreakdownFilter ? new Set(breakdownKeys.filter((k) => !hiddenKeys.has(k))) : null),
    [canBreakdownFilter, breakdownKeys, hiddenKeys]
  );

  const events = useMemo(() => {
    if (!allEvents?.length || kpi.data_shape === "category_compare") return [];
    return allEvents.map((e) => ({ ...e, period_label: yearToPeriodLabel(e.year) }));
  }, [allEvents, kpi.data_shape]);

  const mergedEvents = useMemo(() => (peerCompare ? [] : mergeEventsByPeriod(events)), [events, peerCompare]);

  const targetPlacement = useMemo(() => targetTagPlacement(points, kpi), [points, kpi]);
  const showChartTargets =
    !tableView && !peerCompare && !growthMode && showBenchmark &&
    (kpi.target_value != null || kpi.aspirational_target != null);
  const hasBrush = points.length > 6;

  function handleExportPng() {
    exportChartAsPng(chartRef.current, `${kpi.name.replace(/\s+/g, "_")}.png`);
  }

  function handleExportCsv() {
    if (kpi.data_shape === "category_compare") {
      const breakdown = points[0]?.breakdown || {};
      const subkeys = Object.keys(Object.values(breakdown)[0] || {});
      const rows = [[kpi.breakdown_label || "Category", ...subkeys], ...Object.entries(breakdown).map(([c, v]) => [c, ...subkeys.map((k) => v[k])])];
      downloadCsv(`${kpi.name.replace(/\s+/g, "_")}.csv`, rows);
      return;
    }
    if (kpi.data_shape === "time_breakdown") {
      const keys = Object.keys(points[0]?.breakdown || {});
      const rows = [["Period", ...keys], ...points.map((p) => [p.period_label, ...keys.map((k) => p.breakdown?.[k])])];
      downloadCsv(`${kpi.name.replace(/\s+/g, "_")}.csv`, rows);
      return;
    }
    const hasSecondary = kpi.data_shape === "time_dual";
    const header = ["Period", kpi.name, ...(hasSecondary ? [kpi.secondary_label] : []), "Target"];
    const rows = [header, ...points.map((p) => [p.period_label, p.value, ...(hasSecondary ? [p.secondary_value] : []), p.target_value])];
    downloadCsv(`${kpi.name.replace(/\s+/g, "_")}.csv`, rows);
  }

  return (
    <div
      className={`rounded-2xl border p-5 ${
        hero ? "border-orange-500/30 bg-base-850 shadow-glow" : "border-base-800 bg-base-850"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1 basis-56">
          <p className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-base-500">
            {hero && <span className="rounded-full bg-orange-500/15 px-2 py-0.5 text-orange-400">Headline KPI</span>}
            <span className="truncate">{kpi.category}</span>
          </p>
          <h3 className={`font-semibold text-white ${hero ? "text-lg" : "text-base"}`}>
            {kpi.display_title || kpi.name}
          </h3>
          {kpi.display_title && kpi.display_title !== kpi.name && (
            <p className="text-[11px] text-base-500">{kpi.name}</p>
          )}
          <p className="mt-1 flex flex-wrap items-baseline gap-x-2">
            <span className={`font-bold text-orange-500 ${hero ? "text-3xl sm:text-4xl" : "text-xl"}`}>
              {formatKpiValue(kpi.current_value, kpi.unit)}
            </span>
            {/* Which year this value is for - KPIs don't all share a latest year
                (one might be FY2024-25, another FY2025-26), so this is shown
                unconditionally next to every value, not buried in the source line. */}
            {kpi.period && <span className="text-xs font-medium text-base-500">({kpi.period})</span>}
          </p>
          {kpi.plain_note && (
            <p className="mt-1.5 max-w-prose text-xs leading-relaxed text-base-400">{kpi.plain_note}</p>
          )}
        </div>

        <select
          value={range}
          onChange={(e) => setRange(e.target.value)}
          className="shrink-0 rounded-lg border border-base-700 bg-base-800 px-2 py-1.5 text-xs text-base-200 focus:border-cyan-500 focus:outline-none"
        >
          {RANGES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <KpiProvenance kpi={kpi} currentPeriod={kpi.period} />

      <div className="mb-3 mt-3 flex flex-wrap items-center gap-1.5">
        {canGrowth && (
          <Toggle
            active={growthMode}
            onClick={() => {
              setGrowthMode((g) => !g);
              setPeerCompare(false);
            }}
            title="Toggle absolute value vs YoY % change"
          >
            YoY Growth
          </Toggle>
        )}
        <Toggle
          active={showBenchmark}
          onClick={() => setShowBenchmark((b) => !b)}
          title={
            kpi.aspirational_target != null
              ? `${kpi.benchmark_label} vs ${kpi.aspirational_label}`
              : "Show / hide the target line"
          }
        >
          Targets
        </Toggle>
        {canPeer && (
          <Toggle
            active={peerCompare}
            onClick={() => {
              setPeerCompare((p) => !p);
              setGrowthMode(false);
            }}
            title="Compare first vs latest period"
          >
            2014 vs Now
          </Toggle>
        )}
        <Toggle active={tableView} onClick={() => setTableView((t) => !t)} title="Switch between chart and table view">
          {tableView ? "Chart View" : "Table View"}
        </Toggle>

        <span className="mx-1 h-4 w-px bg-base-700" />

        <button onClick={handleExportPng} className="rounded-full border border-base-700 bg-base-800 px-2.5 py-1 text-[11px] font-medium text-base-400 hover:text-orange-400">
          Export PNG
        </button>
        <button onClick={handleExportCsv} className="rounded-full border border-base-700 bg-base-800 px-2.5 py-1 text-[11px] font-medium text-base-400 hover:text-orange-400">
          Export CSV
        </button>
      </div>

      {canBreakdownFilter && breakdownKeys.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-base-500">{kpi.breakdown_label || "Breakdown"}:</span>
          {breakdownKeys.map((k, i) => {
            const active = !hiddenKeys.has(k);
            return (
              <button
                key={k}
                onClick={() =>
                  setHiddenKeys((prev) => {
                    const next = new Set(prev);
                    if (next.has(k)) next.delete(k);
                    else next.add(k);
                    return next;
                  })
                }
                className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]"
                style={{
                  borderColor: active ? PALETTE[i % PALETTE.length] : "#333",
                  color: active ? PALETTE[i % PALETTE.length] : "#6b6b6b",
                }}
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: active ? PALETTE[i % PALETTE.length] : "#4d4d4d" }} />
                {k}
              </button>
            );
          })}
        </div>
      )}

      {isLoading && <ChartSkeleton height={280} />}
      {isError && <ErrorBanner message={error?.message || "Couldn't load chart data."} onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          {showChartTargets && targetPlacement === "banner" && (
            <ChartTargetTag kpi={kpi} unit={unit} placement="banner" />
          )}
          <div ref={chartRef} className="relative rounded-xl bg-base-850">
            {tableView ? (
              <DataTable kpi={kpi} points={points} />
            ) : (
              <ChartRenderer
                kpi={kpi}
                points={points}
                unit={unit}
                secondaryUnit={secondaryUnit}
                showBenchmark={showBenchmark}
                peerCompare={peerCompare}
                visibleKeys={visibleKeys}
                events={events}
                height={hero ? 340 : 260}
              />
            )}
            {showChartTargets && targetPlacement !== "banner" && (
              <ChartTargetTag kpi={kpi} unit={unit} placement={targetPlacement} hasBrush={hasBrush} />
            )}
          </div>

          {!tableView && mergedEvents.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-base-500">
              {mergedEvents.map((e) => (
                <li key={e.period_label} className="flex items-start gap-1.5">
                  <span className="mt-px flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border border-base-600 text-[9px] text-base-300">
                    {e.index}
                  </span>
                  <span>
                    {e.labels.join("; ")} <span className="text-base-600">· {e.period_label}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
