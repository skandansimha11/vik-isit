const HEADLINE_ICON = {
  // Deterministic Ministry Performance Score labels (see app/scoring.py)
  Strong: "✅",
  Satisfactory: "🙂",
  Mediocre: "⚠️",
  Weak: "⚠️",
  Poor: "❌",
  // Legacy / free-form Tarka labels (compare, freeform verdicts)
  Good: "✅",
  Mixed: "↔️",
};

function HeadlineRow({ headline, timePeriodJudged }) {
  if (!headline && !timePeriodJudged) return null;
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2">
      {headline && (
        <span className="text-sm font-semibold text-white">
          {HEADLINE_ICON[headline] ? `${HEADLINE_ICON[headline]} ${headline}` : headline}
        </span>
      )}
      {timePeriodJudged && (
        <span className="text-[11px] text-base-500">
          Period: <span className="text-base-300">{timePeriodJudged}</span>
        </span>
      )}
    </div>
  );
}

function BulletList({ bullets, tight }) {
  if (!bullets.length) return null;
  return (
    <ul className={`space-y-1.5 text-sm leading-relaxed ${tight ? "text-base-200" : "mb-3 text-base-200"}`}>
      {bullets.map((bullet, i) => (
        <li key={i} className="flex gap-2">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
          <span>{bullet}</span>
        </li>
      ))}
    </ul>
  );
}

// `boxed`: Tarka chat answers. The condensed, conversational `summary` (falling
// back to `evidence` for the deterministic "Explain a KPI" path, which has no
// summary field) is the ONLY thing shown, entirely inside one bordered cyan
// panel - the deeper evidence/caveats/context fields are still returned by the
// API for anyone reading the response directly, just not rendered here.
// Unboxed (the default): the Key Insights panel, already condensed upstream to
// headline + period + bullets, rendered plainly inside its own card.
export default function InsightBody({
  headline,
  timePeriodJudged,
  bullets = [],
  summary = [],
  caveats = [],
  proxyDisclosure,
  comparativeContext,
  forwardImplications,
  inference,
  boxed = false,
}) {
  if (boxed) {
    const points = summary.length ? summary : bullets;
    return (
      <div className="rounded-xl border border-cyan-500/25 bg-cyan-500/5 p-3.5">
        <HeadlineRow headline={headline} timePeriodJudged={timePeriodJudged} />
        <BulletList bullets={points} tight />
      </div>
    );
  }

  return (
    <div>
      <HeadlineRow headline={headline} timePeriodJudged={timePeriodJudged} />

      <BulletList bullets={bullets} />

      {proxyDisclosure && (
        <div className="mb-3 rounded-lg border border-orange-500/20 bg-orange-500/5 p-2.5">
          <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-orange-400">⚠ Proxy metric</p>
          <p className="text-xs text-base-300">{proxyDisclosure}</p>
        </div>
      )}

      {caveats.length > 0 && (
        <div className="mb-3">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-base-500">Caveats</p>
          <ul className="space-y-1">
            {caveats.map((caveat, i) => (
              <li key={i} className="flex gap-2 text-xs text-base-400">
                <span className="mt-0.5 text-cyan-400">•</span>
                <span>{caveat}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {comparativeContext && (
        <p className="mb-2 text-xs text-base-400">
          <span className="font-semibold text-base-300">Context: </span>
          {comparativeContext}
        </p>
      )}

      {(forwardImplications || inference) && (
        <p className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3 text-sm leading-relaxed text-base-200">
          {forwardImplications || inference}
        </p>
      )}
    </div>
  );
}
