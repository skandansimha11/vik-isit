import { useQuery } from "@tanstack/react-query";
import { fetchEvents } from "../api/ministries";

export function useEvents(ministryCode) {
  return useQuery({
    queryKey: ["events", ministryCode || "all"],
    queryFn: () => fetchEvents(ministryCode),
  });
}
