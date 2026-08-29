import { useQuery } from "@tanstack/react-query";
import { fetchMinistries } from "../api/ministries";

export function useMinistries() {
  return useQuery({
    queryKey: ["ministries"],
    queryFn: fetchMinistries,
  });
}
