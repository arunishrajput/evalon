import { useAuthStore } from "@/store/auth";
import type {
  AdminHackathonSummary,
  ApiErrorBody,
  ChatSession,
  ChatMessage,
  ComparisonResponse,
  Criterion,
  CriterionInput,
  DashboardStats,
  Evaluation,
  AgentResultRow,
  Hackathon,
  HackathonSettings,
  ModelStatus,
  Page,
  Participant,
  RankingEntry,
  Submission,
  TokenPair,
  User,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  errorCode: string;

  constructor(status: number, body: Partial<ApiErrorBody>) {
    super(body.detail || "Something went wrong. Please try again.");
    this.status = status;
    this.errorCode = body.error_code || "unknown_error";
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) {
          logout();
          return false;
        }
        const tokens: TokenPair = await res.json();
        setTokens(tokens.access_token, tokens.refresh_token);
        return true;
      } catch {
        logout();
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  skipAuth?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, skipAuth = false } = options;
  const url = buildUrl(path, query);

  const doFetch = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (!skipAuth) {
      const token = useAuthStore.getState().accessToken;
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }
    return fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await doFetch();

  if (res.status === 401 && !skipAuth) {
    const refreshed = await tryRefresh();
    if (refreshed) res = await doFetch();
  }

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await res.json().catch(() => ({})) : undefined;

  if (!res.ok) {
    throw new ApiError(res.status, (payload as ApiErrorBody) || {});
  }
  return payload as T;
}

export function sseUrl(path: string): string {
  return buildUrl(path);
}

// --- Auth ---

export const authApi = {
  register: (email: string, password: string, full_name?: string) =>
    apiFetch<User>("/auth/register", { method: "POST", body: { email, password, full_name }, skipAuth: true }),
  login: (email: string, password: string) =>
    apiFetch<TokenPair>("/auth/login", { method: "POST", body: { email, password }, skipAuth: true }),
  me: () => apiFetch<User>("/auth/me"),
  logout: (refresh_token: string) => apiFetch<void>("/auth/logout", { method: "POST", body: { refresh_token } }),
};

// --- Hackathons ---

export const hackathonApi = {
  list: (page = 1, page_size = 20) =>
    apiFetch<Page<Hackathon>>("/hackathons", { query: { page, page_size } }),
  get: (id: string) => apiFetch<Hackathon>(`/hackathons/${id}`),
  create: (payload: {
    title: string;
    description?: string;
    start_date?: string | null;
    end_date?: string | null;
    max_submissions?: number;
    settings?: Partial<HackathonSettings>;
  }) => apiFetch<Hackathon>("/hackathons", { method: "POST", body: payload }),
  update: (id: string, payload: Record<string, unknown>) =>
    apiFetch<Hackathon>(`/hackathons/${id}`, { method: "PATCH", body: payload }),
  updateStatus: (id: string, status: string) =>
    apiFetch<Hackathon>(`/hackathons/${id}/status`, { method: "PATCH", body: { status } }),
  finalize: (id: string) => apiFetch<Hackathon>(`/hackathons/${id}/finalize`, { method: "POST" }),
  listCriteria: (id: string) => apiFetch<Criterion[]>(`/hackathons/${id}/criteria`),
  replaceCriteria: (id: string, criteria: CriterionInput[]) =>
    apiFetch<Criterion[]>(`/hackathons/${id}/criteria`, { method: "PUT", body: { criteria } }),
  listParticipants: (id: string) => apiFetch<Participant[]>(`/hackathons/${id}/participants`),
  join: (id: string) => apiFetch<Participant>(`/hackathons/${id}/join`, { method: "POST" }),
  listSubmissions: (id: string) => apiFetch<Submission[]>(`/hackathons/${id}/submissions`),
};

// --- Submissions ---

export const submissionApi = {
  create: (hackathon_id: string, repo_url: string) =>
    apiFetch<Submission>("/submissions", { method: "POST", body: { hackathon_id, repo_url } }),
  get: (id: string) => apiFetch<Submission>(`/submissions/${id}`),
  withdraw: (id: string) => apiFetch<void>(`/submissions/${id}`, { method: "DELETE" }),
  statusStreamUrl: (id: string) => sseUrl(`/submissions/${id}/status`),
};

// --- Evaluations ---

export const evaluationApi = {
  get: (submissionId: string) => apiFetch<Evaluation>(`/evaluations/${submissionId}`),
  agents: (submissionId: string) => apiFetch<AgentResultRow[]>(`/evaluations/${submissionId}/agents`),
  retry: (submissionId: string) => apiFetch<Submission>(`/evaluations/${submissionId}/retry`, { method: "POST" }),
  exportPdfUrl: (submissionId: string) => sseUrl(`/evaluations/${submissionId}/export`),
};

// --- Rankings ---

export const rankingApi = {
  leaderboard: (hackathonId: string) => apiFetch<RankingEntry[]>(`/rankings/${hackathonId}`),
  mine: (hackathonId: string) => apiFetch<RankingEntry>(`/rankings/${hackathonId}/me`),
};

// --- Dashboard ---

export const dashboardApi = {
  get: (hackathonId: string) => apiFetch<DashboardStats>(`/dashboard/${hackathonId}`),
  streamUrl: (hackathonId: string) => sseUrl(`/dashboard/${hackathonId}/stream`),
};

// --- Comparison ---

export const comparisonApi = {
  compare: (hackathonId: string, submissionIds: string[]) =>
    apiFetch<ComparisonResponse>(`/compare/${hackathonId}`, { query: { submission_ids: submissionIds.join(",") } }),
};

// --- Chat / mentor ---

export const chatApi = {
  createSession: (submissionId: string) =>
    apiFetch<ChatSession>(`/chat/${submissionId}/sessions`, { method: "POST" }),
  history: (submissionId: string) => apiFetch<ChatMessage[]>(`/chat/${submissionId}/history`),
  messagesUrl: (submissionId: string) => sseUrl(`/chat/${submissionId}/messages`),
};

// --- Admin ---

export const adminApi = {
  modelStatus: () => apiFetch<ModelStatus>("/admin/model/status"),
  hackathons: () => apiFetch<AdminHackathonSummary[]>("/admin/hackathons"),
};

export { API_BASE };
