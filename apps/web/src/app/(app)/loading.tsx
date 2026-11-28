/**
 * Shown at once while a page that was not prefetched loads (ADR-0014): the shell stays, and the content area shows the
 * outline of a page instead of the previous one waiting on a server round trip.
 */
export default function Loading() {
  return (
    <div className="mx-auto max-w-[96rem] space-y-8" aria-busy="true" data-testid="page-loading">
      <span className="sr-only" role="status">
        Loading page…
      </span>
      <div className="space-y-3" aria-hidden>
        <div className="skeleton h-9 w-72 max-w-full rounded-control" />
        <div className="skeleton h-4 w-[28rem] max-w-full rounded-control" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton h-24 rounded-panel" />
        ))}
      </div>
      <div className="skeleton h-72 rounded-panel" aria-hidden />
    </div>
  );
}
