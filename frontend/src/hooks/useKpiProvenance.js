import { useQuery } from "@tanstack/react-query";
import { fetchKpiProvenance } from "../api/ministries";

export function useKpiProvenance(kpiId, { enabled = true } = {}) {
  return useQuery({
    queryKey: ["kpi-provenance", kpiId],
    queryFn: () => fetchKpiProvenance(kpiId),
    enabled: kpiId != null && enabled,
    staleTime: 5 * 60 * 1000,
  });
}
