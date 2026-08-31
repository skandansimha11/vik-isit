import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import { persistQueryCache, restoreQueryCache } from "./lib/queryPersist";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      // Cold starts can take ~30-60s; back off gently rather than hammering.
      retryDelay: (attempt) => Math.min(1500 * 2 ** attempt, 8000),
      refetchOnWindowFocus: false,
      // Serve cached data immediately and revalidate in the background. Longer
      // here = fewer spinners while the free-tier API wakes up.
      staleTime: 5 * 60_000,
      gcTime: 24 * 60 * 60_000,
      networkMode: "always",
    },
    mutations: {
      networkMode: "always",
    },
  },
});

// Rehydrate from localStorage before the first render so cached data paints instantly.
restoreQueryCache(queryClient);
persistQueryCache(queryClient);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
