import { useQuery } from "@tanstack/react-query";
import { fetchMinistryDetail } from "../api/ministries";

export function useMinistryDetail(ministryId) {
  return useQuery({
    queryKey: ["ministry", ministryId],
    queryFn: () => fetchMinistryDetail(ministryId),
    enabled: ministryId != null,
  });
}
