// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("omniscale_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function setToken(token) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("omniscale_token", token);
  }
}

export function clearToken() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem("omniscale_token");
  }
}

export const auth = {
  register: (email, password, fullName) =>
    api.post("/api/v1/auth/register", { email, password, full_name: fullName }),
  login: (email, password) => api.post("/api/v1/auth/login", { email, password }),
  me: () => api.get("/api/v1/auth/me"),
};

export const agent = {
  invoke: (prompt, documentNamespace) =>
    api.post("/api/v1/agent/invoke", { prompt, document_namespace: documentNamespace }),
};

export const rag = {
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/api/v1/rag/documents", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  list: () => api.get("/api/v1/rag/documents"),
  query: (query, namespace, topK = 5) =>
    api.post("/api/v1/rag/query", { query, namespace, top_k: topK }),
};

export const cnn = {
  analyze: (file) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/api/v1/cnn/analyze", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  getJob: (jobId) => api.get(`/api/v1/cnn/jobs/${jobId}`),
};

export const billing = {
  checkout: (tier) => api.post("/api/v1/billing/checkout", { tier }),
  subscription: () => api.get("/api/v1/billing/subscription"),
  usage: () => api.get("/api/v1/billing/usage"),
};
