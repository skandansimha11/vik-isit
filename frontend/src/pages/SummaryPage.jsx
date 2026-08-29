import { Link } from "react-router-dom";
import { useSummary } from "../hooks/useSummary";
import { useMinistries } from "../hooks/useMinistries";
import { GridSkeleton, CardSkeleton } from "../components/Skeletons";
import ErrorBanner from "../components/ErrorBanner";
import ScoreLabelBadge from "../components/ScoreLabelBadge";

function StatCard({ label, value, accent = "text-white", sub, badgeLabel }) {
  return (
    <div className="rounded-2xl border border-base-800 bg-base-850 p-5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-base-500">{label}</p>
      <div className="mt-2 flex items-center gap-2">
        <p className={`text-3xl font-extrabold ${accent}`}>{value}</p>
        {badgeLabel && <ScoreLabelBadge label={badgeLabel} />}
      </div>
      {sub && <p className="mt-1 text-xs text-base-500">{sub}</p>}
    </div>
  );
}

function MinistryRankRow({ ministry, rank }) {
  return (
    <Link
      to={`/ministries/${ministry.id}`}
      className="flex items-center justify-between gap-3 rounded-xl border border-base-800 bg-base-900 px-4 py-3 transition hover:border-orange-500/40"
    >
      <div className="flex items-center gap-3">
        <span className="w-5 text-center text-sm font-bold text-base-600">{rank}</span>
        <span className="text-sm font-medium text-base-200">{ministry.name}</span>
      </div>
      <div className="flex items-center gap-2">
        <ScoreLabelBadge label={ministry.score_label} />
        <span className="text-sm font-bold text-orange-500">{ministry.score?.toFixed(1) ?? "—"}</span>
      </div>
    </Link>
  );
}

export default function SummaryPage() {
  const { data: summary, isLoading: summaryLoading, isError: summaryError, error: sErr, refetch: refetchSummary } = useSummary();
  const { data: ministries, isLoading: ministriesLoading } = useMinistries();

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Executive Summary</h1>
        <p className="mt-1 text-sm text-base-400">Overall government performance, at a glance.</p>
      </div>

      {summaryError && <ErrorBanner message={sErr?.message} onRetry={refetchSummary} />}

      {summaryLoading ? (
        <div className="mb-8"><GridSkeleton count={4} /></div>
      ) : (
        summary && (
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Overall Performance Score"
              value={summary.overall_score != null ? summary.overall_score.toFixed(1) : "—"}
              accent="text-orange-500"
              sub={`Across ${summary.total_ministries} ministries`}
              badgeLabel={summary.overall_label}
            />
            <StatCard label="Improving" value={summary.improving_count} accent="text-positive" sub="ministries trending up" />
            <StatCard label="Declining" value={summary.declining_count} accent="text-negative" sub="ministries trending down" />
            <StatCard label="Steady" value={summary.steady_count} accent="text-base-300" sub="ministries holding flat" />
          </div>
        )
      )}

      {summaryLoading ? (
        <div className="mb-10 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CardSkeleton className="h-64" />
          <CardSkeleton className="h-64" />
        </div>
      ) : (
        summary && (
          <div className="mb-10 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-positive/20 bg-base-850 p-5">
              <h2 className="mb-3 text-sm font-semibold text-positive">Top 3 Performing Ministries</h2>
              <div className="space-y-2">
                {summary.top_ministries.map((m, i) => (
                  <MinistryRankRow key={m.id} ministry={m} rank={i + 1} />
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-negative/20 bg-base-850 p-5">
              <h2 className="mb-3 text-sm font-semibold text-negative">Bottom 3 Underperforming</h2>
              <div className="space-y-2">
                {summary.bottom_ministries.map((m, i) => (
                  <MinistryRankRow key={m.id} ministry={m} rank={i + 1} />
                ))}
              </div>
            </div>
          </div>
        )
      )}

      <div>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-base-500">All Ministries</h2>
        {ministriesLoading ? (
          <GridSkeleton count={10} />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ministries?.map((m) => (
              <Link
                key={m.id}
                to={`/ministries/${m.id}`}
                className="rounded-2xl border border-base-800 bg-base-850 p-5 transition hover:border-orange-500/40 hover:shadow-glow"
              >
                <div className="flex items-center justify-end">
                  <span className="text-xs font-medium capitalize text-base-500">{m.status}</span>
                </div>
                <h3 className="mt-3 text-sm font-semibold text-white">{m.name}</h3>
                <p className="mt-1 line-clamp-2 text-xs text-base-500">{m.description}</p>
                <div className="mt-3 flex items-center gap-2">
                  <p className="text-2xl font-bold text-orange-500">{m.score?.toFixed(1) ?? "—"}</p>
                  <ScoreLabelBadge label={m.score_label} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
