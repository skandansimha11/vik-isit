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

export default function InsightBody({
  headline,
  timePeriodJudged,
  bullets = [],
  caveats = [],
  proxyDisclosure,
  comparativeContext,
  forwardImplications,
  inference,
}) {
  return (
    <div>
      {(headline || timePeriodJudged) && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
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
      )}

      {bullets.length > 0 && (
        <ul className="mb-3 space-y-1.5 text-sm text-base-200">
          {bullets.map((bullet, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-orange-500" />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      )}

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
