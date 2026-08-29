import { useEffect, useState } from "react";
import { useSyncAll } from "../hooks/useSyncAll";

const STATUS_STYLE = {
  updated: "text-positive",
  no_change: "text-base-500",
  unchanged_source: "text-base-500",
  error: "text-negative",
};

export default function SyncButton() {
  const { mutate, isPending, isError, isSuccess, error, data, reset } = useSyncAll();
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    if (isSuccess) {
      setShowSummary(true);
      const timer = setTimeout(() => {
        setShowSummary(false);
        reset();
      }, 12000);
      return () => clearTimeout(timer);
    }
  }, [isSuccess, reset]);

  const rows = data ?? [];
  const updated = rows.filter((r) => r.status === "updated");
  const errors = rows.filter((r) => r.status === "error");

  return (
    <div className="relative flex flex-col items-end gap-1.5">
      <button
        onClick={() => mutate()}
        disabled={isPending}
        className="flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3.5 py-2 text-xs font-medium text-cyan-400 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending && <span className="h-3 w-3 animate-spin rounded-full border-2 border-cyan-400/40 border-t-cyan-400" />}
        {isPending ? "Recomputing…" : "Sync Live Data"}
      </button>

      {isError && <span className="text-xs text-negative">{error?.message || "Sync failed."}</span>}

      {showSummary && !isError && (
        <div className="absolute right-0 top-full z-40 mt-2 w-72 rounded-xl border border-base-700 bg-base-850 p-3 text-xs shadow-2xl">
          <p className="mb-1.5 font-semibold text-base-200">
            Recomputed {rows.length} KPI{rows.length === 1 ? "" : "s"} from curated sources
          </p>
          <p className="mb-2 text-[11px] text-base-500">
            {updated.length} updated · {rows.length - updated.length - errors.length} unchanged
            {errors.length ? ` · ${errors.length} error` : ""}
          </p>
          <ul className="max-h-52 space-y-0.5 overflow-y-auto">
            {(updated.length ? updated : rows).slice(0, 15).map((r, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span className="truncate text-base-300">{r.kpi_name}</span>
                <span className={STATUS_STYLE[r.status] || "text-base-500"}>
                  {r.status === "updated" ? `${r.old_value ?? "—"} → ${r.new_value ?? "—"}` : r.status.replace("_", " ")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
