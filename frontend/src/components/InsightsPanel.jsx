import { useMinistryInsights } from "../hooks/useMinistryInsights";
import ErrorBanner from "./ErrorBanner";
import InsightBody from "./InsightBody";

export default function InsightsPanel({ ministryId }) {
  const { data, isLoading, isError, error, refetch, regenerate, isFetching } = useMinistryInsights(ministryId);

  return (
    <div className="rounded-2xl border border-base-800 bg-base-850 p-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-cyan-400">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-500/15 text-[10px]">✦</span>
          Key insights
        </p>
        {data && (
          <button
            onClick={() => regenerate()}
            disabled={isFetching}
            className="text-[11px] font-medium text-base-500 hover:text-orange-400 disabled:opacity-50"
          >
            {isFetching ? "Refreshing…" : "Regenerate"}
          </button>
        )}
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-3 w-full animate-pulse rounded bg-base-800" />
          ))}
        </div>
      )}

      {isError && <ErrorBanner compact message={error?.message || "Couldn't load insights."} onRetry={refetch} />}

      {!isLoading && !isError && data && (
        <div>
          <InsightBody
            headline={data.headline}
            timePeriodJudged={data.time_period_judged}
            bullets={data.bullets}
            caveats={data.caveats}
            proxyDisclosure={data.proxy_disclosure}
            comparativeContext={data.comparative_context}
            inference={data.inference}
          />
          <p className="mt-3 text-[11px] text-base-600">
            Generated {new Date(data.generated_at).toLocaleString()}
            {data.cached && " · cached"}
          </p>
        </div>
      )}
    </div>
  );
}
