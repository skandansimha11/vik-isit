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

function fmtMonth(ym) {
  if (!ym || !/^\d{4}-\d{2}$/.test(ym)) return ym || "";
  const [y, m] = ym.split("-");
  return `${["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m]} ${y}`;
}

function Chevron({ open }) {
  return (
    <svg
      viewBox="0 0 12 12"
      className={`h-2.5 w-2.5 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 2l4 4-4 4" />
    </svg>
  );
}

function Row({ label, children }) {
  return (
    <>
      <dt className="text-base-500">{label}</dt>
      <dd className="min-w-0 text-base-300">{children}</dd>
    </>
  );
}

export default function KpiProvenance({ kpi, currentPeriod }) {
  const [open, setOpen] = useState(false);
  const { data: prov } = useKpiProvenance(kpi.id, { enabled: open && kpi.is_live });

  const rev = kpi.data_version;

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 text-[11px] font-medium text-base-500 hover:text-base-300"
      >
        <Chevron open={open} />
        Sources &amp; data quality
      </button>

      {open && (
        <div className="mt-2 rounded-lg border border-base-800 bg-base-900/60 p-4">
          {!kpi.is_live ? (
            <p className="text-xs leading-relaxed text-base-400">
              Illustrative placeholder data. This KPI is not yet wired to a live source.
            </p>
          ) : (
            <>
              <dl className="grid grid-cols-[minmax(88px,auto)_1fr] gap-x-4 gap-y-2.5 text-xs">
                {kpi.data_quality && (
                  <Row label="Data quality">
                    <span
                      className={`inline-flex rounded-full border px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide ${
                        QUALITY_STYLE[kpi.data_quality] || QUALITY_STYLE.MEDIUM
                      }`}
                    >
                      {kpi.data_quality}
                    </span>
                  </Row>
                )}
                <Row label="Proxy metric">
                  {kpi.is_proxy ? "Yes, an indirect stand-in for the true measure" : "No, measured directly"}
                </Row>
                <Row label="Source">
                  {kpi.source_url ? (
                    <a
                      href={kpi.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-words text-base-300 underline decoration-dotted underline-offset-2 hover:text-cyan-400"
                    >
                      {kpi.source_name}
                    </a>
                  ) : (
                    kpi.source_name || "-"
                  )}
                </Row>
                {(currentPeriod || rev || kpi.source_updated_at) && (
                  <Row label="Latest data">
                    <span className="flex flex-wrap gap-x-1.5">
                      {currentPeriod && <span>{currentPeriod}</span>}
                      {rev && <span className="text-base-500">· {REVISION_LABEL[rev] || rev}</span>}
                      {kpi.source_updated_at && (
                        <span className="text-base-500">· published {fmtMonth(kpi.source_updated_at)}</span>
                      )}
                    </span>
                  </Row>
                )}
              </dl>

              {prov && (prov.definition || prov.formula || prov.caveats?.length || prov.unresolved?.length || prov.datasets?.length) && (
                <div className="mt-3 space-y-2.5 border-t border-base-800 pt-3 text-[11px] text-base-400">
                  {prov.definition && (
                    <p className="leading-relaxed">
                      <span className="font-semibold text-base-300">Definition. </span>
                      {prov.definition}
                    </p>
                  )}
                  {prov.formula && <p className="font-mono text-[10px] text-base-500">{prov.formula}</p>}
                  {prov.caveats?.length > 0 && (
                    <div>
                      <p className="font-semibold text-base-300">Caveats</p>
                      <ul className="mt-1 space-y-1">
                        {prov.caveats.map((c, i) => (
                          <li key={i} className="flex gap-1.5">
                            <span className="text-cyan-500">•</span>
                            <span className="leading-relaxed">{c}</span>
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
                      <ul className="mt-1 space-y-1">
                        {prov.unresolved.slice(0, 6).map((u, i) => (
                          <li key={i}>
                            {u.period} - {u.source_doc} ({u.page_ref})
                          </li>
                        ))}
                      </ul>
                      {prov.unresolved.length > 6 && (
                        <p className="mt-1 text-base-600">
                          + {prov.unresolved.length - 6} more - see <code>data/tier_a/GAPS.md</code>
                        </p>
                      )}
                    </div>
                  )}
                  {prov.datasets?.length > 0 && (
                    <p className="text-base-600">Data files: {prov.datasets.join(", ")}</p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
