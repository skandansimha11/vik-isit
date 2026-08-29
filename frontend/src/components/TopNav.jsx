import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useMinistries } from "../hooks/useMinistries";
import SyncButton from "./SyncButton";

const linkBase =
  "px-3 py-2 text-sm font-medium rounded-lg transition-colors";
const linkActive = "text-orange-500 bg-orange-500/10";
const linkInactive = "text-base-300 hover:text-white hover:bg-base-800";

export default function TopNav() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { data: ministries, isLoading, isError } = useMinistries();

  // Close the menu on any outside interaction (pointerdown covers mouse + touch
  // + pen), on Escape, and whenever the route changes.
  useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    function onKeyDown(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  return (
    <header className="sticky top-0 z-30 border-b border-base-800 bg-base-900/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <nav className="flex flex-1 flex-wrap items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive} flex items-center gap-1.5 shrink-0`}
          >
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <path
                d="M2 7.2 7.5 2.5l5.5 4.7M3.3 6.2v5.8h8.4V6.2"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Home
          </NavLink>

          <NavLink to="/summary" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
            View Summary
          </NavLink>

          <div className="relative" ref={ref}>
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
              className={`${linkBase} ${linkInactive} flex items-center gap-1`}
            >
              Analyze Ministries
              <svg width="12" height="12" viewBox="0 0 12 12" className={`transition-transform ${open ? "rotate-180" : ""}`}>
                <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            {open && (
              <div
                role="menu"
                className="absolute left-0 top-full z-50 mt-2 max-h-[min(80vh,26rem)] w-72 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-xl border border-base-700 bg-base-850 p-1.5 shadow-2xl"
              >
                <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-base-500">
                  Select a ministry
                </p>
                {ministries?.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setOpen(false);
                      navigate(`/ministries/${m.id}`);
                    }}
                    className="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm text-base-200 hover:bg-base-800"
                  >
                    <span className="truncate">{m.name}</span>
                    <span className="shrink-0 text-xs text-base-500">{m.score != null ? `${m.score}` : "—"}</span>
                  </button>
                ))}
                {!ministries?.length && (
                  <p className="px-3 py-2 text-sm text-base-500">
                    {isLoading
                      ? "Loading ministries…"
                      : isError
                      ? "Couldn't reach the API — is the backend running on :8000?"
                      : "No ministries loaded yet."}
                  </p>
                )}
              </div>
            )}
          </div>

          <NavLink to="/chatbot" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
            Ask Tarka AI
          </NavLink>
        </nav>

        {/* Dev-only: recomputes KPIs from the curated CSVs. Hidden in production builds
            (Vite's import.meta.env.DEV is false once `vite build` runs, e.g. on Vercel) —
            a public showcase shouldn't invite visitors to poke at the sync pipeline. */}
        {import.meta.env.DEV && <SyncButton />}
      </div>
    </header>
  );
}
