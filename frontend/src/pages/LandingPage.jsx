import { Link } from "react-router-dom";
import { useMinistries } from "../hooks/useMinistries";
import TarkaLogo from "../components/chat/TarkaLogo";
import logo from "../assets/logo.png";

const BLOCKS = [
  {
    title: "Live Ministry KPIs",
    icon: "📊",
    accent: "orange",
    body: "All 10 ministries are tracked against 3 headline KPIs each, computed from a curated, provenance-tracked layer of official filings, budget documents and surveys, refreshed on demand via the connector pipeline.",
  },
  {
    title: "10-Year Trend Analysis",
    icon: "📈",
    accent: "cyan",
    body: "Each KPI is one clean trend line since FY2014-15, with its official and aspirational targets as a shaded band and major policy events marked underneath.",
  },
  {
    title: "Key insights",
    icon: "✦",
    accent: "orange",
    body: "Every ministry page ships with a 3-bullet briefing plus a one-paragraph inference, drawn directly from the underlying KPI data.",
  },
  {
    title: "Ask Tarka AI",
    icon: null,
    accent: "cyan",
    body: "Tarka, the analytical policy chatbot, answers questions about any ministry's numbers, trends, or comparisons, framework-grounded, with evidence and caveats every time.",
  },
];

const ACCENT_STYLES = {
  orange: {
    ring: "border-orange-500/25 hover:border-orange-500/50",
    badge: "bg-orange-500/15 text-orange-400",
    bar: "from-orange-500 via-orange-500/40 to-transparent",
    glow: "hover:shadow-glow",
  },
  cyan: {
    ring: "border-cyan-500/25 hover:border-cyan-500/50",
    badge: "bg-cyan-500/15 text-cyan-400",
    bar: "from-cyan-500 via-cyan-500/40 to-transparent",
    glow: "hover:shadow-glow-cyan",
  },
};

export default function LandingPage() {
  const { data: ministries } = useMinistries();

  return (
    <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-3xl text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-400">
          10 Ministries · 30 KPIs · FY2014-15 to FY2025-26
        </span>
        <div className="mt-6 flex justify-center">
          <img
            src={logo}
            alt="vik-isit Ministry Performance Analysis"
            className="h-32 w-auto rounded-3xl shadow-glow sm:h-40 [filter:saturate(1.35)_contrast(1.08)_brightness(1.04)]"
          />
        </div>
        <p className="mt-4 text-base leading-relaxed text-base-400 sm:text-lg">
          A single place to analyze how India&rsquo;s ministries are performing: fiscal discipline, industrial output,
          infrastructure, welfare and energy, with key insights on every page.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/summary"
            className="rounded-lg bg-orange-500 px-6 py-3 text-sm font-semibold text-black shadow-glow transition hover:bg-orange-400"
          >
            Explore the Analysis →
          </Link>
          <Link
            to="/chatbot"
            className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-6 py-3 text-sm font-semibold text-cyan-400 transition hover:bg-cyan-500/20"
          >
            Ask Tarka AI
          </Link>
        </div>
      </div>

      <div className="mt-16 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {BLOCKS.map((b) => {
          const accent = ACCENT_STYLES[b.accent];
          return (
            <div
              key={b.title}
              className={`group relative overflow-hidden rounded-2xl border bg-base-850 p-6 shadow-lg shadow-black/20 transition duration-200 ${accent.ring} ${accent.glow}`}
            >
              <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${accent.bar}`} />
              <span className={`flex h-12 w-12 items-center justify-center rounded-xl text-2xl ${accent.badge}`}>
                {b.icon ?? <TarkaLogo className="h-7 w-7" />}
              </span>
              <h3 className="mt-4 text-base font-bold text-white">{b.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-base-400">{b.body}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-16">
        <h2 className="mb-4 text-center text-sm font-semibold uppercase tracking-wide text-base-500">
          Jump straight to a ministry
        </h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {ministries?.map((m) => (
            <Link
              key={m.id}
              to={`/ministries/${m.id}`}
              className="flex items-center justify-between gap-2 rounded-xl border border-base-800 bg-base-850 px-3 py-2.5 text-xs font-medium text-base-300 transition hover:border-orange-500/40 hover:text-orange-400"
            >
              <span>{m.code}</span>
              <span className="text-base-600">{m.score != null ? m.score.toFixed(0) : "-"}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
