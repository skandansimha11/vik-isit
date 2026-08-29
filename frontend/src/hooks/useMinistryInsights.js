import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchMinistryInsights } from "../api/ministries";

export function useMinistryInsights(ministryId, { enabled = true } = {}) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["insights", ministryId],
    queryFn: () => fetchMinistryInsights(ministryId),
    enabled: enabled && ministryId != null,
    staleTime: Infinity,
    retry: 0,
  });

  const regenerate = () =>
    queryClient.fetchQuery({
      queryKey: ["insights", ministryId],
      queryFn: () => fetchMinistryInsights(ministryId, { force: true }),
    });

  return { ...query, regenerate };
}
