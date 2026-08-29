export default function ErrorBanner({ message, onRetry, compact = false }) {
  return (
    <div
      className={`rounded-lg border border-negative/30 bg-negative/10 text-negative ${
        compact ? "px-3 py-2 text-xs" : "px-4 py-3 text-sm"
      }`}
    >
      <p>{message || "Something went wrong."}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1.5 font-medium text-orange-500 underline decoration-dotted underline-offset-2 hover:text-orange-400"
        >
          Try again
        </button>
      )}
    </div>
  );
}
