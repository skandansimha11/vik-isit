// Maps app.scoring.SCORE_BANDS labels to theme-consistent badge styling.
// Strong/Satisfactory/Mediocre/Weak/Poor — see app/scoring.py for the thresholds.
const STYLES = {
  Strong: "border-positive/30 bg-positive/10 text-positive",
  Satisfactory: "border-cyan-500/30 bg-cyan-500/10 text-cyan-400",
  Mediocre: "border-orange-500/30 bg-orange-500/10 text-orange-400",
  Weak: "border-orange-700/40 bg-orange-700/10 text-orange-500",
  Poor: "border-negative/30 bg-negative/10 text-negative",
};

export default function ScoreLabelBadge({ label, size = "sm" }) {
  if (!label) return null;
  const style = STYLES[label] || "border-base-700 bg-base-800 text-base-300";
  const sizing = size === "lg" ? "px-3 py-1 text-xs" : "px-2 py-0.5 text-[10px]";
  return (
    <span className={`inline-flex items-center rounded-full border font-semibold uppercase tracking-wide ${sizing} ${style}`}>
      {label}
    </span>
  );
}
