import { useMutation } from "@tanstack/react-query";
import { postChat } from "../api/ministries";

export function useChat() {
  return useMutation({
    mutationFn: postChat,
  });
}
