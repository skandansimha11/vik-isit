import { useMutation } from "@tanstack/react-query";
import { askTarka, compareTarka, explainTarkaKpi, focusTarka, trendTarka } from "../api/ministries";

export function useTarkaAsk() {
  return useMutation({ mutationFn: askTarka });
}

export function useTarkaCompare() {
  return useMutation({ mutationFn: compareTarka });
}

export function useTarkaExplain() {
  return useMutation({ mutationFn: explainTarkaKpi });
}

export function useTarkaTrend() {
  return useMutation({ mutationFn: trendTarka });
}

export function useTarkaFocus() {
  return useMutation({ mutationFn: focusTarka });
}
