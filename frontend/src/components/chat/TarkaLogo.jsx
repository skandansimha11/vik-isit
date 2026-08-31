import { useId } from "react";

// A diya (oil lamp) - the traditional Indian symbol of knowledge dispelling
// darkness, standing in for Tarka ("reasoning/logic" in Sanskrit): the flame
// is the insight, the lamp is the analytical framework that holds it steady.
export default function TarkaLogo({ className = "h-8 w-8" }) {
  const uid = useId();
  const flameId = `tarka-flame-${uid}`;
  const diyaId = `tarka-diya-${uid}`;

  return (
    <svg viewBox="0 0 48 48" className={className} fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id={flameId} x1="24" y1="6" x2="24" y2="25" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FF8A5E" />
          <stop offset="100%" stopColor="#FF6B35" />
        </linearGradient>
        <linearGradient id={diyaId} x1="5" y1="19" x2="43" y2="37" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#3EE4FF" />
          <stop offset="100%" stopColor="#00A8C7" />
        </linearGradient>
      </defs>

      {/* diya vessel - a shallow boat-shaped lamp with pointed wick ends */}
      <path
        d="M4 27 Q24 18.5 44 27 Q24 38 4 27 Z"
        stroke={`url(#${diyaId})`}
        strokeWidth="2.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* a hint of oil pooled in the base */}
      <path d="M13 27.5 Q24 32 35 27.5" stroke={`url(#${diyaId})`} strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />

      {/* flame */}
      <path
        d="M24 6.5 C29 12.5 31 17.5 24 24.5 C17 17.5 19 12.5 24 6.5 Z"
        fill={`url(#${flameId})`}
      />
    </svg>
  );
}
