import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartTooltip from "./ChartTooltip";
import { formatAxisTick } from "../../utils/format";

export const PALETTE = ["#00D9FF", "#FF6B35", "#22c55e", "#a78bfa", "#f472b6", "#facc15"];

const axisTick = { fontSize: 11, fill: "#8f8f8f" };
const gridProps = { stroke: "#262626", strokeDasharray: "3 3", vertical: false };
// Generous bottom room so rotated ticks + brush never collide with anything below.
const baseMargin = { top: 16, right: 18, left: 4, bottom: 4 };

const xAxisProps = {
  tick: axisTick,
  axisLine: { stroke: "#333" },
  tickLine: false,
  tickMargin: 10,
  minTickGap: 4,
};
const yAxisProps = {
  tick: axisTick,
  axisLine: false,
  tickLine: false,
  width: 56,
  tickMargin: 6,
  tickFormatter: formatAxisTick,
};

function tip(unitMap) {
  function BoundTooltip(props) {
    return <ChartTooltip {...props} unitMap={unitMap} />;
  }
  return BoundTooltip;
}

// ---------------------------------------------------------------- events
// Multiple events can fall on the same period (2020 has three). Merge them so
// exactly one dashed marker + one numbered badge renders per period — numbered
// badges sit far apart on the x-axis and never overlap; the full list is shown
// as a caption under the chart by ChartCard (see mergeEventsByPeriod export).
export function mergeEventsByPeriod(events = []) {
  const byPeriod = new Map();
  for (const e of events) {
    if (!e?.period_label) continue;
    if (!byPeriod.has(e.period_label)) byPeriod.set(e.period_label, []);
    byPeriod.get(e.period_label).push(e);
  }
  return [...byPeriod.entries()]
    .map(([period_label, evs]) => ({
      period_label,
      year: evs[0].year,
      labels: evs.map((e) => e.label),
    }))
    .sort((a, b) => (a.year ?? 0) - (b.year ?? 0))
    .map((e, i) => ({ ...e, index: i + 1 }));
}

function EventBadge(index) {
  function Badge({ viewBox }) {
    if (!viewBox) return null;
    const cx = viewBox.x;
    const cy = viewBox.y + 8;
    return (
      <g pointerEvents="none">
        <circle cx={cx} cy={cy} r={7} fill="#1a1a1a" stroke="#6b6b6b" strokeWidth={1} />
        <text x={cx} y={cy + 0.5} textAnchor="middle" dominantBaseline="central" fontSize={9} fill="#b3b3b3">
          {index}
        </text>
      </g>
    );
  }
  return Badge;
}

function eventLines(mergedEvents, yAxisId) {
  return mergedEvents.map((e) => (
    <ReferenceLine
      key={e.period_label}
      x={e.period_label}
      yAxisId={yAxisId}
      stroke="#4d4d4d"
      strokeDasharray="2 3"
      label={EventBadge(e.index)}
    />
  ));
}

// Official (solid) + aspirational (dotted) target lines, with a faint band
// between them. `yAxisId` only where the chart has multiple axes.
function targetOverlay({ official, aspirational, yAxisId }) {
  const els = [];
  const common = yAxisId ? { yAxisId } : {};
  if (official != null && aspirational != null && official !== aspirational) {
    els.push(
      <ReferenceArea
        key="tgt-band"
        {...common}
        y1={Math.min(official, aspirational)}
        y2={Math.max(official, aspirational)}
        fill="#22c55e"
        fillOpacity={0.06}
        ifOverflow="extendDomain"
      />
    );
  }
  // No on-chart text labels — the band + two line styles read cleanly, and the
  // card's target readout ("Target X → aspiration Y") carries the numbers.
  // One short marker on the official line only, at the left edge.
  if (official != null) {
    els.push(
      <ReferenceLine
        key="tgt-official"
        {...common}
        y={official}
        stroke="#8f8f8f"
        strokeDasharray="6 4"
        ifOverflow="extendDomain"
        label={{ value: `target ${formatAxisTick(official)}`, position: "insideTopLeft", fill: "#9a9a9a", fontSize: 9 }}
      />
    );
  }
  if (aspirational != null && aspirational !== official) {
    els.push(
      <ReferenceLine
        key="tgt-asp"
        {...common}
        y={aspirational}
        stroke="#22c55e"
        strokeDasharray="2 4"
        strokeOpacity={0.7}
        ifOverflow="extendDomain"
      />
    );
  }
  return els;
}

function keysOf(obj) {
  return obj ? Object.keys(obj) : [];
}

function filterKeys(keys, visibleKeys) {
  if (!visibleKeys) return keys;
  return keys.filter((k) => visibleKeys.has(k));
}

const legendProps = {
  verticalAlign: "top",
  align: "left",
  iconSize: 9,
  wrapperStyle: { fontSize: 11, color: "#b3b3b3", paddingBottom: 4, lineHeight: "15px" },
};

// A top legend with several series wraps onto multiple rows on narrow screens
// (and inside the half-width cards of the desktop grid). Recharts does not
// reserve vertical space for the wrapped rows, so a wrapped row lands on top of
// the first Y-axis tick. Estimate the row count deliberately conservatively —
// over-reserving just adds a little whitespace above the plot; under-reserving
// causes the overlap we are trying to prevent. Returns px to reserve.
const ONE_ROW_LEGEND = 22;

function legendReserveFor(keys) {
  const list = (keys || []).filter(Boolean);
  if (list.length <= 1) return ONE_ROW_LEGEND;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1024;
  // assume a fairly narrow container (mobile, or a half-width desktop card)
  const avail = Math.min(Math.max(160, vw - 130), 420);
  let row = 0;
  let rows = 1;
  for (const k of list) {
    const w = String(k).length * 8 + 30; // generous: icon + gap + 11px label
    if (row + w > avail && row > 0) {
      rows += 1;
      row = w;
    } else {
      row += w;
    }
  }
  return rows * 18 + 8;
}

// legendReserve: px to reserve above the plot for the legend (0 / false = none).
function marginWith({ brush = false, legendReserve = 0, rotatedTicks = false } = {}) {
  return {
    ...baseMargin,
    top: baseMargin.top + (legendReserve || 0),
    bottom: baseMargin.bottom + (brush ? 26 : 0) + (rotatedTicks ? 26 : 0),
  };
}

function isConstant(vals) {
  const nums = vals.filter((v) => v != null);
  if (nums.length < 2) return true;
  return Math.max(...nums) - Math.min(...nums) < 0.06;
}

// ---------------------------------------------------------------- line/bar
function LineTimeChart({ points, unit, showBenchmark, events, height, targets }) {
  const data = points.map((p) => ({ period_label: p.period_label, value: p.value, target: p.target_value }));
  const targetVals = data.map((d) => d.target);
  const constant = isConstant(targetVals);
  const official = constant ? targetVals.find((v) => v != null) ?? targets?.official : null;
  const glidePath = showBenchmark && !constant && targetVals.some((v) => v != null);
  const brush = data.length > 6;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={marginWith({ brush })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} domain={["auto", "auto"]} />
        <Tooltip content={tip({ value: unit, target: unit })} />
        {showBenchmark &&
          targetOverlay({
            official: official ?? targets?.official,
            aspirational: targets?.aspirational,
            officialLabel: targets?.officialLabel,
            aspirationalLabel: targets?.aspirationalLabel,
          })}
        {glidePath && (
          <Line type="monotone" dataKey="target" name={targets?.officialLabel || "Target"} stroke="#8f8f8f" strokeDasharray="5 4" dot={false} strokeWidth={1.5} isAnimationActive={false} />
        )}
        <Line type="monotone" dataKey="value" name="Value" stroke="#FF6B35" strokeWidth={2.5} dot={{ r: 3, fill: "#FF6B35" }} activeDot={{ r: 5 }} isAnimationActive={false} />
        {eventLines(events)}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

function BarTimeChart({ points, unit, showBenchmark, events, height, targets }) {
  const data = points.map((p) => ({ period_label: p.period_label, value: p.value, target: p.target_value }));
  const official = data.find((d) => d.target != null)?.target ?? targets?.official;
  const brush = data.length > 6;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={marginWith({ brush })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip({ value: unit })} />
        {showBenchmark &&
          targetOverlay({
            official,
            aspirational: targets?.aspirational,
            officialLabel: targets?.officialLabel,
            aspirationalLabel: targets?.aspirationalLabel,
          })}
        <Bar dataKey="value" name="Value" fill="#FF6B35" radius={[4, 4, 0, 0]} maxBarSize={44} isAnimationActive={false} />
        {eventLines(events)}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ------------------------------------------------------------- breakdown
function MultiLineBreakdownChart({ points, visibleKeys, events, height, unit, targets }) {
  const keys = filterKeys(keysOf(points[0]?.breakdown), visibleKeys);
  const data = points.map((p) => ({ period_label: p.period_label, ...p.breakdown }));
  const unitMap = Object.fromEntries(keys.map((k) => [k, unit]));
  const brush = data.length > 6;
  const legendReserve = legendReserveFor(keys);
  return (
    <ResponsiveContainer width="100%" height={height + legendReserve}>
      <LineChart data={data} margin={marginWith({ brush, legendReserve })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip(unitMap)} />
        <Legend {...legendProps} height={legendReserve} />
        {targets && targetOverlay(targets)}
        {keys.map((k, i) => (
          <Line key={k} type="monotone" dataKey={k} name={k} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
        ))}
        {eventLines(events)}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </LineChart>
    </ResponsiveContainer>
  );
}

function StackedAreaChart({ points, visibleKeys, events, height, unit, targets }) {
  const keys = filterKeys(keysOf(points[0]?.breakdown), visibleKeys);
  const data = points.map((p) => ({ period_label: p.period_label, ...p.breakdown }));
  const unitMap = Object.fromEntries(keys.map((k) => [k, unit]));
  const brush = data.length > 6;
  const legendReserve = legendReserveFor(keys);
  return (
    <ResponsiveContainer width="100%" height={height + legendReserve}>
      <AreaChart data={data} margin={marginWith({ brush, legendReserve })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip(unitMap)} />
        <Legend {...legendProps} height={legendReserve} />
        {targets?.official != null && (
          <ReferenceLine
            y={targets.official}
            stroke="#8f8f8f"
            strokeDasharray="6 4"
            ifOverflow="extendDomain"
            label={{ value: `rail target ${formatAxisTick(targets.official)}`, position: "insideRight", fill: "#9a9a9a", fontSize: 9 }}
          />
        )}
        {keys.map((k, i) => (
          <Area
            key={k}
            type="monotone"
            dataKey={k}
            name={k}
            stackId="1"
            stroke={PALETTE[i % PALETTE.length]}
            fill={PALETTE[i % PALETTE.length]}
            fillOpacity={0.5}
            isAnimationActive={false}
          />
        ))}
        {eventLines(events)}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Grouped bars over time (one group of N bars per period). Used by the
// Tax Harassment KPI (time_breakdown + grouped_bar).
function GroupedBarBreakdownChart({ points, visibleKeys, events, height, unit }) {
  const keys = filterKeys(keysOf(points[0]?.breakdown), visibleKeys);
  const data = points.map((p) => ({ period_label: p.period_label, ...p.breakdown }));
  const unitMap = Object.fromEntries(keys.map((k) => [k, unit]));
  const brush = data.length > 8;
  const legendReserve = legendReserveFor(keys);
  return (
    <ResponsiveContainer width="100%" height={height + legendReserve}>
      <BarChart data={data} margin={marginWith({ brush, legendReserve })} barGap={1} barCategoryGap="18%">
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip(unitMap)} />
        <Legend {...legendProps} height={legendReserve} />
        {keys.map((k, i) => (
          <Bar key={k} dataKey={k} name={k} fill={PALETTE[i % PALETTE.length]} radius={[3, 3, 0, 0]} maxBarSize={22} isAnimationActive={false} />
        ))}
        {eventLines(events)}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </BarChart>
    </ResponsiveContainer>
  );
}

// -------------------------------------------------------------- dual/time_dual
function DualAxisChart({ points, primaryLabel, secondaryLabel, unit, secondaryUnit, events, height }) {
  const data = points.map((p) => ({ period_label: p.period_label, value: p.value, secondary: p.secondary_value }));
  const brush = data.length > 6;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={marginWith({ brush, legendReserve: ONE_ROW_LEGEND })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis yAxisId="left" {...yAxisProps} />
        <YAxis yAxisId="right" orientation="right" {...yAxisProps} />
        <Tooltip content={tip({ value: unit, secondary: secondaryUnit })} />
        <Legend {...legendProps} height={ONE_ROW_LEGEND} />
        <Line yAxisId="left" type="monotone" dataKey="value" name={primaryLabel} stroke="#FF6B35" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
        <Line yAxisId="right" type="monotone" dataKey="secondary" name={secondaryLabel} stroke="#00D9FF" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
        {eventLines(events, "left")}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function GroupedBarTimeChart({ points, primaryLabel, secondaryLabel, showBenchmark, unit, secondaryUnit, events, height }) {
  const data = points.map((p) => ({ period_label: p.period_label, value: p.value, secondary: p.secondary_value }));
  const brush = data.length > 6;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={marginWith({ brush, legendReserve: ONE_ROW_LEGEND })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip({ value: unit, secondary: secondaryUnit })} />
        <Legend {...legendProps} height={ONE_ROW_LEGEND} />
        {showBenchmark && <Bar dataKey="value" name={primaryLabel} fill="#4d4d4d" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />}
        <Bar dataKey="secondary" name={secondaryLabel} fill="#00D9FF" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
        {eventLines(events)}
        {brush && <Brush dataKey="period_label" height={18} stroke="#FF6B35" fill="#1a1a1a" travellerWidth={8} y={height - 22} />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------- category_compare
// A tick that wraps long category labels onto up to 3 short lines instead of
// letting a single angled string overrun its neighbour.
function WrappedTick({ x, y, payload, width }) {
  const text = String(payload.value ?? "");
  const perLine = Math.max(8, Math.floor((width || 90) / 6.2));
  const words = text.split(/\s+/);
  const lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > perLine && cur) {
      lines.push(cur);
      cur = w;
    } else {
      cur = (cur + " " + w).trim();
    }
  }
  if (cur) lines.push(cur);
  const shown = lines.slice(0, 3);
  if (lines.length > 3) shown[2] = shown[2].replace(/.{1}$/, "…");
  return (
    <g transform={`translate(${x},${y + 8})`}>
      {shown.map((ln, i) => (
        <text key={i} x={0} y={i * 11} textAnchor="middle" fontSize={10} fill="#8f8f8f">
          {ln}
        </text>
      ))}
    </g>
  );
}

// Horizontal tick for the vertical (horizontal-bar) layout.
function HBarTick({ x, y, payload }) {
  const text = String(payload.value ?? "");
  const shown = text.length > 26 ? text.slice(0, 25) + "…" : text;
  return (
    <text x={x - 4} y={y} textAnchor="end" dominantBaseline="central" fontSize={10} fill="#8f8f8f">
      {shown}
    </text>
  );
}

function CategoryChart({ points, subkeyMode, unit, height, stacked }) {
  const breakdown = points[0]?.breakdown || {};
  const categories = Object.keys(breakdown);
  const subkeys = Object.keys(breakdown[categories[0]] || {});
  const data = categories.map((c) => ({ category: c, ...breakdown[c] }));
  const visibleSubkeys = stacked ? subkeys : subkeyMode === "all" ? subkeys : subkeys.slice(0, 1);
  const unitMap = Object.fromEntries(subkeys.map((k) => [k, unit]));

  const maxLabel = Math.max(0, ...categories.map((c) => c.length));
  // Long or numerous labels -> horizontal bars, which never crowd.
  const horizontal = maxLabel > 13 || categories.length > 5;

  if (horizontal) {
    return (
      <ResponsiveContainer width="100%" height={Math.max(height, categories.length * (stacked ? 46 : visibleSubkeys.length * 24 + 22))}>
        <BarChart layout="vertical" data={data} margin={{ ...baseMargin, left: 8, right: 22 }} barCategoryGap="22%">
          <CartesianGrid {...gridProps} horizontal={false} vertical />
          <XAxis type="number" {...yAxisProps} width={undefined} height={24} />
          <YAxis type="category" dataKey="category" width={150} tick={HBarTick} axisLine={{ stroke: "#333" }} tickLine={false} interval={0} />
          <Tooltip content={tip(unitMap)} />
          <Legend {...legendProps} height={ONE_ROW_LEGEND} />
          {visibleSubkeys.map((k, i) => (
            <Bar
              key={k}
              dataKey={k}
              name={k}
              stackId={stacked ? "a" : undefined}
              fill={i === 0 && !stacked ? "#FF6B35" : PALETTE[i % PALETTE.length]}
              radius={stacked ? 0 : [0, 3, 3, 0]}
              maxBarSize={26}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height + 20}>
      <BarChart data={data} margin={{ ...baseMargin, bottom: 40 }} barCategoryGap="20%">
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="category" tick={<WrappedTick width={Math.max(60, 720 / Math.max(1, categories.length))} />} axisLine={{ stroke: "#333" }} tickLine={false} interval={0} height={44} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip(unitMap)} />
        <Legend {...legendProps} height={ONE_ROW_LEGEND} />
        {visibleSubkeys.map((k, i) => (
          <Bar
            key={k}
            dataKey={k}
            name={k}
            stackId={stacked ? "a" : undefined}
            fill={i === 0 && !stacked ? "#FF6B35" : PALETTE[i % PALETTE.length]}
            radius={stacked ? (i === visibleSubkeys.length - 1 ? [4, 4, 0, 0] : 0) : [4, 4, 0, 0]}
            maxBarSize={30}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// -------------------------------------------------------------- peer compare
function PeerCompareChart({ kpi, points, unit, secondaryUnit, height }) {
  const first = points[0];
  const last = points[points.length - 1];
  const shape = kpi.data_shape;

  if (shape === "time_breakdown") {
    const keys = keysOf(first.breakdown);
    const data = [
      { period_label: first.period_label, ...first.breakdown },
      { period_label: last.period_label, ...last.breakdown },
    ];
    const unitMap = Object.fromEntries(keys.map((k) => [k, unit]));
    const legendReserve = legendReserveFor(keys);
    return (
      <ResponsiveContainer width="100%" height={height + legendReserve}>
        <BarChart data={data} margin={marginWith({ legendReserve })}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="period_label" {...xAxisProps} />
          <YAxis {...yAxisProps} />
          <Tooltip content={tip(unitMap)} />
          <Legend {...legendProps} height={legendReserve} />
          {keys.map((k, i) => (
            <Bar key={k} dataKey={k} name={k} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} maxBarSize={60} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  const data = [
    { period_label: first.period_label, value: first.value, secondary: first.secondary_value },
    { period_label: last.period_label, value: last.value, secondary: last.secondary_value },
  ];
  const hasSecondary = shape === "time_dual";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={marginWith({ legendReserve: hasSecondary ? ONE_ROW_LEGEND : 0 })}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="period_label" {...xAxisProps} />
        <YAxis {...yAxisProps} />
        <Tooltip content={tip({ value: unit, secondary: secondaryUnit })} />
        {hasSecondary && <Legend {...legendProps} height={ONE_ROW_LEGEND} />}
        <Bar dataKey="value" name={kpi.name} fill="#FF6B35" radius={[4, 4, 0, 0]} maxBarSize={60} isAnimationActive={false} />
        {hasSecondary && <Bar dataKey="secondary" name={kpi.secondary_label} fill="#00D9FF" radius={[4, 4, 0, 0]} maxBarSize={60} isAnimationActive={false} />}
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------- entrypoint
export default function ChartRenderer({
  kpi,
  points,
  unit,
  secondaryUnit,
  showBenchmark = true,
  peerCompare = false,
  visibleKeys = null,
  events = [],
  height = 280,
}) {
  if (!points?.length) {
    return <p className="p-6 text-center text-sm text-base-500">No data available for this range.</p>;
  }

  const mergedEvents = mergeEventsByPeriod(events);
  const targets = {
    official: kpi.target_value || null,
    aspirational: kpi.aspirational_target ?? null,
    officialLabel: kpi.benchmark_label || "Target",
    aspirationalLabel: kpi.aspirational_label || "Aspiration",
  };

  if (peerCompare && ["time_line", "time_dual", "time_breakdown"].includes(kpi.data_shape) && points.length >= 2) {
    return <PeerCompareChart kpi={kpi} points={points} unit={unit} secondaryUnit={secondaryUnit} height={height} />;
  }

  const shape = kpi.data_shape;
  const type = kpi.chart_type;

  if (shape === "time_line" && type === "line")
    return <LineTimeChart points={points} unit={unit} showBenchmark={showBenchmark} events={mergedEvents} height={height} targets={targets} />;
  if (shape === "time_line" && type === "bar")
    return <BarTimeChart points={points} unit={unit} showBenchmark={showBenchmark} events={mergedEvents} height={height} targets={targets} />;
  if (shape === "time_breakdown" && type === "line")
    return <MultiLineBreakdownChart points={points} unit={unit} visibleKeys={visibleKeys} events={mergedEvents} height={height} targets={showBenchmark ? targets : null} />;
  if (shape === "time_breakdown" && type === "stacked_area")
    return <StackedAreaChart points={points} unit={unit} visibleKeys={visibleKeys} events={mergedEvents} height={height} targets={showBenchmark ? targets : null} />;
  if (shape === "time_breakdown" && type === "grouped_bar")
    return <GroupedBarBreakdownChart points={points} unit={unit} visibleKeys={visibleKeys} events={mergedEvents} height={height} />;
  if (shape === "time_dual" && type === "dual_axis")
    return (
      <DualAxisChart
        points={points}
        primaryLabel={kpi.name}
        secondaryLabel={kpi.secondary_label}
        unit={unit}
        secondaryUnit={secondaryUnit}
        events={mergedEvents}
        height={height}
      />
    );
  if (shape === "time_dual" && type === "grouped_bar")
    return (
      <GroupedBarTimeChart
        points={points}
        primaryLabel={kpi.benchmark_label || "Budget"}
        secondaryLabel={kpi.secondary_label}
        showBenchmark={showBenchmark}
        unit={unit}
        secondaryUnit={secondaryUnit}
        events={mergedEvents}
        height={height}
      />
    );
  if (shape === "category_compare" && (type === "grouped_bar" || type === "bar"))
    return <CategoryChart points={points} subkeyMode={showBenchmark ? "all" : "primary"} unit={unit} height={height} />;
  if (shape === "category_compare" && type === "stacked_bar")
    return <CategoryChart points={points} unit={unit} height={height} stacked />;

  return <p className="p-6 text-sm text-base-500">Unsupported chart configuration.</p>;
}
