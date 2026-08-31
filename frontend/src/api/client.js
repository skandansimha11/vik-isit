import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL,
  // The API runs on a free tier that cold-starts in ~30-60s after idle, so the
  // first request of a session can be slow. Give it room rather than failing.
  timeout: 65_000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.message ||
      "Unexpected error talking to the API.";
    return Promise.reject(new Error(message));
  }
);

export default apiClient;
