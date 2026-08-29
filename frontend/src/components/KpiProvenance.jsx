import { useState } from "react";
import { useKpiProvenance } from "../hooks/useKpiProvenance";

const QUALITY_STYLE = {
  HIGH: "border-positive/40 bg-positive/10 text-positive",
  MEDIUM: "border-orange-500/40 bg-orange-500/10 text-orange-400",
  LOW: "border-negative/40 bg-negative/10 text-negative",
};

const REVISION_LABEL = {
  Actual: "Actual",
  Provisional: "Provisional",
  Revised: "Revised Estimate",
  BudgetEstimate: "Budget Estimate",
  Estimated: "Estimated",
};

const REVISION_STYLE = {
  Actual: "text-base-400",
  Provisional: "text-base-300",
  Revised: "text-base-300",
  BudgetEstimate: "text-orange-400",
  Estimated: "text-orange-400",
};

function fmtMonth(ym) {
  if (!ym || !/^\d{4}-\d{2}$/.test(ym)) return ym || "";
  const [y, m] = ym.split("-");
  return `${["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m]} ${y}`;
}

export default function KpiProvenance({ kpi, currentPeriod }) {
  const [open, setOpen] = useState(false);
  const { data: prov } = useKpiProvenance(kpi.id, { enabled: open });

  if (!kpi.is_live) {
    return (
      <p className="mt-1 text-[11px] text-base-600">
        Illustrative placeholder data — this KPI is not yet wired to a live source.
      </p>
    );
  }

  const rev = kpi.data_version;
  return (
    <div className="mt-1.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] leading-tight text-base-500">
        {kpi.data_quality && (
          <span
            className={`rounded-full border px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide ${
              QUALITY_STYLE[kpi.data_quality] || QUALITY_STYLE.MEDIUM
            }`}
          >
            {kpi.data_quality} quality
          </span>
        )}
        {kpi.is_proxy && (
          <span className="rounded-full border border-orange-500/40 bg-orange-500/10 px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide text-orange-400">
            Proxy metric
          </span>
        )}
        <span className="min-w-0">
          Source:{" "}
          {kpi.source_url ? (
            <a
              href={kpi.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-base-400 underline decoration-dotted underline-offset-2 hover:text-cyan-400"
            >
              {kpi.source_name}
            </a>
          ) : (
            <span className="text-base-400">{kpi.source_name}</span>
          )}
        </span>
        {currentPeriod && <span>· latest {currentPeriod}</span>}
        {rev && (
          <span className={REVISION_STYLE[rev] || "text-base-400"}>
            · {REVISION_LABEL[rev] || rev}
          </span>
        )}
        {kpi.source_updated_at && <span>· as published {fmtMonth(kpi.source_updated_at)}</span>}
        <button
          onClick={() => setOpen((o) => !o)}
          className="text-base-500 underline decoration-dotted underline-offset-2 hover:text-orange-400"
        >
          {open ? "hide details" : "provenance"}
        </button>
      </div>

      {open && prov && (
        <div className="mt-2 space-y-2 rounded-lg border border-base-800 bg-base-900/60 p-3 text-[11px] text-base-400">
          {prov.definition && (
            <p>
              <span className="font-semibold text-base-300">Definition. </span>
              {prov.definition}
            </p>
          )}
          {prov.formula && (
            <p className="font-mono text-[10px] text-base-500">{prov.formula}</p>
          )}
          {prov.caveats?.length > 0 && (
            <div>
              <p className="font-semibold text-base-300">Caveats</p>
              <ul className="mt-0.5 space-y-0.5">
                {prov.caveats.map((c, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span className="text-cyan-500">•</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {prov.unresolved?.length > 0 && (
            <div>
              <p className="font-semibold text-orange-400">
                {prov.unresolved.length} data point{prov.unresolved.length === 1 ? "" : "s"} pending confirmation
              </p>
              <ul className="mt-0.5 space-y-0.5">
                {prov.unresolved.slice(0, 6).map((u, i) => (
                  <li key={i}>
                    {u.period} — {u.source_doc} ({u.page_ref})
                  </li>
                ))}
              </ul>
              {prov.unresolved.length > 6 && (
                <p className="mt-0.5 text-base-600">
                  + {prov.unresolved.length - 6} more — see <code>data/tier_a/GAPS.md</code>
                </p>
              )}
            </div>
          )}
          {prov.datasets?.length > 0 && (
            <p className="text-base-600">
              Data files: {prov.datasets.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
