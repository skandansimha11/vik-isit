export function LineSkeleton({ className = "" }) {
  return <div className={`animate-pulse rounded bg-base-800 ${className}`} />;
}

export function CardSkeleton({ className = "" }) {
  return (
    <div className={`rounded-2xl border border-base-800 bg-base-850 p-5 ${className}`}>
      <LineSkeleton className="mb-3 h-3 w-1/3" />
      <LineSkeleton className="mb-2 h-8 w-2/3" />
      <LineSkeleton className="h-3 w-1/2" />
    </div>
  );
}

export function ChartSkeleton({ height = 260 }) {
  return (
    <div className="rounded-2xl border border-base-800 bg-base-850 p-5">
      <LineSkeleton className="mb-4 h-3 w-1/4" />
      <LineSkeleton style={{ height }} className="w-full" />
    </div>
  );
}

export function GridSkeleton({ count = 6 }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}
