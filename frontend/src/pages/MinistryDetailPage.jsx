import { useNavigate, useParams } from "react-router-dom";
import { useMinistryDetail } from "../hooks/useMinistryDetail";
import { useMinistries } from "../hooks/useMinistries";
import ErrorBanner from "../components/ErrorBanner";
import { CardSkeleton, ChartSkeleton } from "../components/Skeletons";
import ChartCard from "../components/charts/ChartCard";
import InsightsPanel from "../components/InsightsPanel";
import ChatWidget from "../components/chat/ChatWidget";

export default function MinistryDetailPage() {
  const { ministryId } = useParams();
  const navigate = useNavigate();
  const id = Number(ministryId);

  const { data: ministry, isLoading, isError, error, refetch } = useMinistryDetail(id);
  const { data: allMinistries } = useMinistries();

  if (isError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <ErrorBanner message={error?.message || "Couldn't load this ministry."} onRetry={refetch} />
      </div>
    );
  }

  if (isLoading || !ministry) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <CardSkeleton className="mb-6 h-20" />
        <ChartSkeleton height={340} />
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      </div>
    );
  }

  const hero = ministry.kpis.find((k) => k.hero) || ministry.kpis[0];
  const others = ministry.kpis.filter((k) => k.id !== hero?.id);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-white">{ministry.name}</h1>
          <p className="mt-1 max-w-2xl text-sm text-base-400">{ministry.description}</p>
        </div>

        <select
          value={id}
          onChange={(e) => navigate(`/ministries/${e.target.value}`)}
          className="w-full shrink-0 rounded-lg border border-base-700 bg-base-850 px-3 py-2 text-sm text-base-200 focus:border-cyan-500 focus:outline-none sm:w-auto"
        >
          {allMinistries?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>

      {hero && (
        <div className="mb-4">
          <ChartCard kpi={hero} ministryCode={ministry.code} hero />
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {others.map((k) => (
          <ChartCard key={k.id} kpi={k} ministryCode={ministry.code} />
        ))}
      </div>

      <div className="mb-6">
        <InsightsPanel ministryId={ministry.id} />
      </div>

      <ChatWidget
        ministryId={ministry.id}
        ministryName={ministry.name}
        kpis={ministry.kpis}
        suggestions={[
          `Why is ${hero?.display_title || hero?.name} moving this way?`,
          "How does this ministry compare to others?",
          "What should I watch next quarter?",
        ]}
      />
    </div>
  );
}
