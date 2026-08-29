const SOURCES = [
  ["Finance", "Union Budget · Economic Survey · CBDT · CAG"],
  ["Petroleum & Natural Gas", "PPAC (Ready Reckoner / Snapshot)"],
  ["Agriculture & Farmers Welfare", "MoSPI National Accounts · CPI · PPAC · NABARD"],
  ["Railways", "Indian Railways Year Book · PIB · FOIS"],
  ["Power", "PFC Report on Performance of Power Utilities · CEA"],
  ["Commerce & Industry", "DGCI&S · MoSPI (GVA / IIP) · DPIIT (PLI)"],
  ["Defence", "Union Budget (Defence Services Estimates) · MoD / DDP · Standing Committee on Defence"],
  ["Education", "ASER (Pratham) · NAS · UDISE+"],
  ["Skill Development & Labour", "MoSPI PLFS · MSDE (Outcome Budget) · EPFO payroll"],
  ["Road Transport & Highways", "MoRTH / NHAI · NCAER–DPIIT logistics study · NITI Aayog"],
];

export default function Footer() {
  return (
    <footer className="mt-12 border-t border-base-800 px-4 py-8 text-xs text-base-600 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-base-500">
          <span className="font-semibold text-base-400">Data provenance.</span> All 30 KPIs across the
          10 ministries are computed from a curated, provenance-tracked layer of official sources —
          every figure carries a revision status (Actual / Provisional / Revised / Budget Estimate /
          Estimated) and links back to its source document. Where no official series exists (e.g.
          industrial import dependence, defence equipment vintage, exam-integrity incidents) the
          number is an assembled estimate, flagged <span className="text-orange-400">Estimated</span>{" "}
          and labelled a proxy on the card.
        </p>
        <ul className="mt-3 grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCES.map(([m, s]) => (
            <li key={m}>
              <span className="text-base-400">{m}:</span> {s}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-base-600">
          Figures flagged Estimated or Budget Estimate are provisional and should be confirmed
          against the cited primary document.
        </p>
      </div>
    </footer>
  );
}
