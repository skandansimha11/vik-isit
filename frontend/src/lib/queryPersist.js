// Lightweight localStorage persistence for the React Query cache.
//
// Why: the API is on a free Render instance that sleeps after 15 min idle and
// takes ~30-60s to cold-start. Without this, a reload during that window shows
// spinners for a minute. With it, the last good data paints instantly from
// localStorage and React Query silently revalidates once the server is up.
//
// Built on the `dehydrate` / `hydrate` primitives that ship with
// @tanstack/react-query, so there's no extra dependency.
import { dehydrate, hydrate } from "@tanstack/react-query";

const KEY = "vikisit:" + "query-cache:v1";
const MAX_AGE_MS = 1000 * 60 * 60 * 24; // drop anything older than a day
const WRITE_DEBOUNCE_MS = 900;

export function restoreQueryCache(queryClient) {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return;
    const { savedAt, state } = JSON.parse(raw);
    if (!savedAt || Date.now() - savedAt > MAX_AGE_MS) {
      localStorage.removeItem(KEY);
      return;
    }
    hydrate(queryClient, state);
  } catch {
    // private mode, corrupt JSON, quota, SSR - just start cold
  }
}

export function persistQueryCache(queryClient) {
  let timer;
  const flush = () => {
    try {
      const state = dehydrate(queryClient, {
        shouldDehydrateQuery: (q) => q.state.status === "success" && q.state.data !== undefined,
      });
      localStorage.setItem(KEY, JSON.stringify({ savedAt: Date.now(), state }));
    } catch {
      // quota / serialization - non-fatal
    }
  };
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(flush, WRITE_DEBOUNCE_MS);
  };
  queryClient.getQueryCache().subscribe(schedule);
  if (typeof window !== "undefined") {
    window.addEventListener("pagehide", flush);
    window.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") flush();
    });
  }
}
