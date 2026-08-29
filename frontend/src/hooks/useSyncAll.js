import { useMutation, useQueryClient } from "@tanstack/react-query";
import { syncAllData } from "../api/ministries";

export function useSyncAll() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: syncAllData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ministries"] });
      queryClient.invalidateQueries({ queryKey: ["ministry"] });
      queryClient.invalidateQueries({ queryKey: ["kpi-history"] });
      queryClient.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}
