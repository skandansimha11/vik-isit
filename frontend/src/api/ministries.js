import apiClient from "./client";

export async function fetchMinistries() {
  const { data } = await apiClient.get("/ministries");
  return data;
}

export async function fetchMinistryDetail(ministryId) {
  const { data } = await apiClient.get(`/ministries/${ministryId}`);
  return data;
}

export async function fetchMinistryInsights(ministryId, { force = false } = {}) {
  const { data } = await apiClient.post(`/ministries/${ministryId}/insights`, null, {
    params: force ? { force: true } : undefined,
  });
  return data;
}

export async function fetchKpiHistory(kpiId, range = "full") {
  const { data } = await apiClient.get(`/kpis/${kpiId}/history`, { params: { range } });
  return data;
}

export async function fetchKpiProvenance(kpiId) {
  const { data } = await apiClient.get(`/kpis/${kpiId}/provenance`);
  return data;
}

export async function fetchSummary() {
  const { data } = await apiClient.get("/summary");
  return data;
}

export async function fetchEvents(ministryCode) {
  const { data } = await apiClient.get("/events", {
    params: ministryCode ? { ministry_code: ministryCode } : undefined,
  });
  return data;
}

export async function postChat({ message, ministryId = null, history = [] }) {
  const { data } = await apiClient.post("/chat", {
    message,
    ministry_id: ministryId,
    history,
  });
  return data;
}

export async function syncAllData() {
  const { data } = await apiClient.post("/sync");
  return data;
}

// --- Tarka chatbot -----------------------------------------------------------

export async function askTarka({ ministryId, question }) {
  const { data } = await apiClient.post("/tarka/ask", { ministry_id: ministryId, question });
  return data;
}

export async function compareTarka({ ministryId1, ministryId2, aspect = "" }) {
  const { data } = await apiClient.post("/tarka/compare", {
    ministry_id_1: ministryId1,
    ministry_id_2: ministryId2,
    aspect,
  });
  return data;
}

export async function explainTarkaKpi({ ministryId, kpiName }) {
  const { data } = await apiClient.post("/tarka/explain", { ministry_id: ministryId, kpi_name: kpiName });
  return data;
}

export async function trendTarka({ ministryId, timePeriod = "" }) {
  const { data } = await apiClient.post("/tarka/trend", { ministry_id: ministryId, time_period: timePeriod });
  return data;
}

export async function focusTarka(ministryId) {
  const { data } = await apiClient.get(`/tarka/focus/${ministryId}`);
  return data;
}
