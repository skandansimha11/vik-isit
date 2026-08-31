import { useMemo, useRef, useState } from "react";
import { useKpiHistory } from "../../hooks/useKpiHistory";
import { useEvents } from "../../hooks/useEvents";
import { downloadCsv, formatKpiValue, trendColor } from "../../utils/format";
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

function TargetReadout({ kpi }) {
  const official = kpi.target_value || null;
  const asp = kpi.aspirational_target ?? null;
  if (official == null && asp == null) return null;
  const cur = kpi.current_value;
  let distance = null;
  if (official != null && cur != null) {
    const gap = kpi.higher_is_better ? official - cur : cur - official;
    distance =
      Math.abs(gap) < 0.05
        ? "on target"
        : gap > 0
        ? `${formatKpiValue(Math.abs(gap), "")} ${kpi.higher_is_better ? "below" : "above"} target`
        : `past target`;
  }
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-base-500">
      {official != null && (
        <span>
          <span className="text-base-400">Target</span> {formatKpiValue(official, kpi.unit)}
        </span>
      )}
      {asp != null && (
        <span>
          <span className="text-positive/80">Aspiration</span> {formatKpiValue(asp, kpi.unit)}
        </span>
      )}
      {distance && <span className="text-base-600">{distance}</span>}
    </div>
  );
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
  const [percentMode, setPercentMode] = useState(false);
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [peerCompare, setPeerCompare] = useState(false);
  const [tableView, setTableView] = useState(false);
  const [hiddenKeys, setHiddenKeys] = useState(() => new Set());
  const chartRef = useRef(null);

  const { data: rawPoints, isLoading, isError, error, refetch } = useKpiHistory(kpi.id, range);
  const { data: allEvents } = useEvents(ministryCode);

  const canGrowth = kpi.data_shape === "time_line";
  const canPercent = !!kpi.target_value && ["time_line", "time_dual"].includes(kpi.data_shape);
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

    if (percentMode && canPercent) {
      // Direction-aware, mirroring the backend's KPI.progress_pct (app/models.py):
      // higher-is-better -> value/target (100% = at target, >100% = beating it).
      // lower-is-better  -> target/value (100% = at target, >100% = beating it too —
      // e.g. Fiscal Deficit at 4.0 vs a 4.3 target is "108% of target", not "93%").
      // A naive value/target for a lower-is-better KPI would show >100% while the
      // metric is actually WORSE than target, which reads backwards next to every
      // other chart where >100% means better.
      const transformed = rawPoints.map((p) => {
        if (p.value == null) return { ...p, value: null, target_value: 100 };
        const ratio = kpi.higher_is_better ? p.value / kpi.target_value : kpi.target_value / p.value;
        return { ...p, value: Math.round(ratio * 1000) / 10, target_value: 100 };
      });
      return { points: transformed, unit: "% of target", secondaryUnit: kpi.secondary_unit };
    }

    return { points: rawPoints, unit: kpi.unit, secondaryUnit: kpi.secondary_unit };
  }, [rawPoints, growthMode, percentMode, canGrowth, canPercent, kpi.target_value, kpi.unit, kpi.secondary_unit]);

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
            <span className={`text-xs font-medium ${trendColor(kpi.trend)}`}>
              {kpi.trend === "up" ? "▲ improving" : kpi.trend === "down" ? "▼ worsening" : "– flat"}
            </span>
          </p>
          {kpi.plain_note && (
            <p className="mt-1.5 max-w-prose text-xs leading-relaxed text-base-400">{kpi.plain_note}</p>
          )}
          <TargetReadout kpi={kpi} />
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
        {canPercent && (
          <Toggle active={percentMode} onClick={() => setPercentMode((p) => !p)} title="Toggle absolute vs % of target">
            % of Target
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
          <div ref={chartRef} className="rounded-xl bg-base-850">
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
