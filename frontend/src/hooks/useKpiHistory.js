import { useQuery } from "@tanstack/react-query";
import { fetchKpiHistory } from "../api/ministries";

export function useKpiHistory(kpiId, range = "full") {
  return useQuery({
    queryKey: ["kpi-history", kpiId, range],
    queryFn: () => fetchKpiHistory(kpiId, range),
    enabled: kpiId != null,
  });
}
