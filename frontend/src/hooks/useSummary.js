import { useQuery } from "@tanstack/react-query";
import { fetchSummary } from "../api/ministries";

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: fetchSummary,
  });
}
