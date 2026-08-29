import { useEffect, useRef, useState } from "react";
import { useTarkaAsk, useTarkaCompare, useTarkaExplain, useTarkaFocus, useTarkaTrend } from "../../hooks/useTarka";
import { useMinistries } from "../../hooks/useMinistries";
import InsightBody from "../InsightBody";
import TarkaLogo from "./TarkaLogo";

function toTarkaMessage(answer, label) {
  return {
    type: "tarka",
    label,
    headline: answer.headline,
    bullets: answer.evidence,
    caveats: answer.caveats,
    timePeriodJudged: answer.time_period_judged,
    dataQualityFlag: answer.data_quality_flag,
    proxyDisclosure: answer.proxy_disclosure,
    comparativeContext: answer.comparative_context,
    forwardImplications: answer.forward_implications,
  };
}

export default function ChatWidget({ ministryId = null, ministryName = null, kpis = [], suggestions = [] }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pickedMinistryId, setPickedMinistryId] = useState(ministryId ?? "");
  const [compareTargetId, setCompareTargetId] = useState("");
  const [explainKpi, setExplainKpi] = useState("");
  const scrollRef = useRef(null);

  const { data: allMinistries } = useMinistries();
  const askTarka = useTarkaAsk();
  const compareTarka = useTarkaCompare();
  const explainTarka = useTarkaExplain();
  const trendTarka = useTarkaTrend();
  const focusTarka = useTarkaFocus();

  const isPending =
    askTarka.isPending || compareTarka.isPending || explainTarka.isPending || trendTarka.isPending || focusTarka.isPending;

  const activeMinistryId = ministryId ?? (pickedMinistryId ? Number(pickedMinistryId) : null);
  const activeMinistryName = ministryId ? ministryName : allMinistries?.find((m) => m.id === activeMinistryId)?.name;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isPending]);

  function pushUser(text) {
    setMessages((prev) => [...prev, { type: "user", text }]);
  }

  function pushError(err) {
    setMessages((prev) => [
      ...prev,
      { type: "error", text: err.message || "Tarka is unavailable right now. Check API credits." },
    ]);
  }

  function pushTarka(answer, label) {
    setMessages((prev) => [...prev, toTarkaMessage(answer, label)]);
  }

  function send() {
    if (!input.trim() || isPending || !activeMinistryId) return;
    const question = input;
    pushUser(question);
    setInput("");
    askTarka.mutate(
      { ministryId: activeMinistryId, question },
      { onSuccess: (data) => pushTarka(data), onError: pushError }
    );
  }

  function runTrend() {
    if (isPending || !activeMinistryId) return;
    pushUser("Trend analysis");
    trendTarka.mutate(
      { ministryId: activeMinistryId },
      { onSuccess: (data) => pushTarka(data, "Trend analysis"), onError: pushError }
    );
  }

  function runFocus() {
    if (isPending || !activeMinistryId) return;
    pushUser("What should I focus on?");
    focusTarka.mutate(activeMinistryId, {
      onSuccess: (data) =>
        setMessages((prev) => [
          ...prev,
          {
            type: "tarka",
            label: "Focus areas",
            headline: `Focus areas for ${data.ministry}`,
            bullets: data.focus_areas,
            caveats: [],
            forwardImplications: data.rationale,
          },
        ]),
      onError: pushError,
    });
  }

  function runExplain(kpiName) {
    if (!kpiName || isPending || !activeMinistryId) return;
    pushUser(`Explain: ${kpiName}`);
    setExplainKpi("");
    explainTarka.mutate(
      { ministryId: activeMinistryId, kpiName },
      { onSuccess: (data) => pushTarka(data, "Explain KPI"), onError: pushError }
    );
  }

  function runCompare(otherId) {
    if (!otherId || isPending || !activeMinistryId) return;
    const other = allMinistries?.find((m) => m.id === Number(otherId));
    pushUser(`Compare with ${other?.name || "another ministry"}`);
    setCompareTargetId("");
    compareTarka.mutate(
      { ministryId1: activeMinistryId, ministryId2: Number(otherId) },
      { onSuccess: (data) => pushTarka(data, "Comparison"), onError: pushError }
    );
  }

  const comparableMinistries = allMinistries?.filter((m) => m.id !== activeMinistryId) || [];

  return (
    <div className="flex flex-col rounded-2xl border border-base-800 bg-base-850">
      <div className="flex items-center gap-2.5 border-b border-base-800 px-5 py-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-base-900 ring-1 ring-inset ring-orange-500/25">
          <TarkaLogo className="h-6 w-6" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-white">Tarka AI</h3>
          <p className="text-xs text-base-500">
            {activeMinistryName ? `Analytical policy assistant · ${activeMinistryName}` : "Analytical policy assistant"}
          </p>
        </div>
      </div>

      {!ministryId && (
        <div className="border-b border-base-800 px-5 py-3">
          <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-base-500">
            Ask about
          </label>
          <select
            value={pickedMinistryId}
            onChange={(e) => {
              setPickedMinistryId(e.target.value);
              setMessages([]);
            }}
            className="w-full rounded-lg border border-base-700 bg-base-900 px-3 py-2 text-sm text-base-200 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">Select a ministry…</option>
            {allMinistries?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div ref={scrollRef} className="flex max-h-96 min-h-[16rem] flex-col gap-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 py-6 text-center">
            <p className="text-sm text-base-500">
              {activeMinistryName
                ? `Ask Tarka about ${activeMinistryName}'s KPIs, trends, or targets.`
                : "Select a ministry above to start asking Tarka."}
            </p>
            {activeMinistryId && suggestions.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setInput(s);
                    }}
                    className="rounded-full border border-base-700 bg-base-800 px-3 py-1.5 text-xs text-base-300 hover:border-cyan-500/50 hover:text-cyan-400"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.type === "user" ? "justify-end" : "justify-start"}`}>
            {m.type === "user" && (
              <div className="max-w-[85%] rounded-2xl bg-orange-500 px-4 py-2.5 text-sm leading-relaxed text-black">
                {m.text}
              </div>
            )}

            {m.type === "error" && (
              <div className="max-w-[85%] rounded-2xl border border-negative/30 bg-negative/10 px-4 py-2.5 text-sm leading-relaxed text-negative">
                {m.text}
              </div>
            )}

            {m.type === "tarka" && (
              <div className="max-w-[90%] rounded-2xl border border-cyan-500/20 bg-base-800 px-4 py-3.5 text-sm">
                {m.label && <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-cyan-400">{m.label}</p>}
                <InsightBody
                  headline={m.headline}
                  dataQualityFlag={m.dataQualityFlag}
                  timePeriodJudged={m.timePeriodJudged}
                  bullets={m.bullets}
                  caveats={m.caveats}
                  proxyDisclosure={m.proxyDisclosure}
                  comparativeContext={m.comparativeContext}
                  forwardImplications={m.forwardImplications}
                />
              </div>
            )}
          </div>
        ))}

        {isPending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl border border-base-700 bg-base-800 px-4 py-2.5">
              {[0, 1, 2].map((i) => (
                <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-400" style={{ animationDelay: `${i * 0.12}s` }} />
              ))}
            </div>
          </div>
        )}
      </div>

      {activeMinistryId && (
        <div className="flex flex-wrap gap-2 border-t border-base-800 px-3 pt-3">
          <button
            onClick={runTrend}
            disabled={isPending}
            className="rounded-full border border-base-700 bg-base-800 px-3 py-1.5 text-xs text-base-300 hover:border-cyan-500/50 hover:text-cyan-400 disabled:opacity-40"
          >
            Trend analysis
          </button>
          <button
            onClick={runFocus}
            disabled={isPending}
            className="rounded-full border border-base-700 bg-base-800 px-3 py-1.5 text-xs text-base-300 hover:border-cyan-500/50 hover:text-cyan-400 disabled:opacity-40"
          >
            Focus areas
          </button>

          {kpis.length > 0 && (
            <select
              value={explainKpi}
              onChange={(e) => runExplain(e.target.value)}
              disabled={isPending}
              className="rounded-full border border-base-700 bg-base-800 px-3 py-1.5 text-xs text-base-300 hover:border-cyan-500/50 disabled:opacity-40"
            >
              <option value="">Explain a KPI…</option>
              {kpis.map((k) => (
                <option key={k.id} value={k.name}>
                  {k.name}
                </option>
              ))}
            </select>
          )}

          {comparableMinistries.length > 0 && (
            <select
              value={compareTargetId}
              onChange={(e) => runCompare(e.target.value)}
              disabled={isPending}
              className="rounded-full border border-base-700 bg-base-800 px-3 py-1.5 text-xs text-base-300 hover:border-cyan-500/50 disabled:opacity-40"
            >
              <option value="">Compare with…</option>
              {comparableMinistries.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex items-center gap-2 border-t border-base-800 p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={activeMinistryId ? "Ask Tarka a question…" : "Select a ministry first…"}
          disabled={!activeMinistryId}
          className="flex-1 rounded-lg border border-base-700 bg-base-900 px-3.5 py-2.5 text-sm text-base-100 placeholder:text-base-500 focus:border-cyan-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isPending || !input.trim() || !activeMinistryId}
          className="rounded-lg bg-orange-500 px-4 py-2.5 text-sm font-medium text-black transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
