/**
 * Typed client for the Fluid-Buddha backend admin API. Attaches the JWT bearer
 * token to every request and throws a friendly ApiError on non-2xx responses.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8080";

/** WebSocket base the embedded widget connects to (`data-backend`). Defaults to
 *  the API host over ws(s). */
export const WIDGET_BACKEND =
  process.env.NEXT_PUBLIC_WIDGET_BACKEND?.replace(/\/$/, "") || API_BASE.replace(/^http/, "ws");

/** Where the SDK bundle is hosted (the install snippet's `<script src>`).
 *  Defaults to the SDK's local `npm run serve:demo` server. */
export const SDK_URL =
  process.env.NEXT_PUBLIC_SDK_URL || "http://localhost:4000/dist/fluid-buddha.global.js";

const TOKEN_KEY = "fb_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  form?: FormData;
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, auth = true, form } = opts;
  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  let payload: BodyInit | undefined;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) throw new ApiError(res.status, errorMessage(data, res.statusText));
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** A readable message from an error body. FastAPI validation errors (422) carry
 *  a list of `{loc, msg}` entries, shown here as "field: message". */
function errorMessage(data: unknown, fallback: string): string {
  const body = (data && typeof data === "object" ? data : {}) as { detail?: unknown; message?: unknown };
  const detail = body.detail ?? body.message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d: { loc?: unknown[]; msg?: string }) => {
      const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body").join(".") : "";
      const msg = (d.msg ?? "invalid").replace(/^Value error, /, "");
      return field ? `${field}: ${msg}` : msg;
    });
    if (parts.length) return parts.join("; ");
  }
  return fallback || "Request failed";
}

// ---- domain types ----------------------------------------------------------
export type Tenant = { id: string; email: string; name: string | null };
export type AuthResponse = { access_token: string; token_type: string; tenant: Tenant };

export type Website = {
  id: string;
  site_key: string;
  /** Widget key embedded in the install snippet; null for sites created before keys existed. */
  public_key: string | null;
  name: string;
  domain: string | null;
  intelligence: string;
  design: string;
  accent: string | null;
  status: string;
  created_at: string;
};

export type Persona = { slug: string; label: string; focus: string; tone: string; landing: string };

export type AgentProfile = {
  site_key: string;
  agent_name: string;
  company_name: string;
  brand_voice: string;
  personas: Persona[];
  closing_use_case: string;
  routes: string[];
  dynamic_prefixes: string[];
};

export type WidgetConfig = {
  site_key: string;
  intelligence: string;
  design: string | null;
  accent: string | null;
  agent_name: string;
  company_name: string;
};

export type Readiness = { status: string; db: boolean; mock_ai: boolean };

export type Source = {
  id: string;
  kind: string;
  name: string;
  status: string;
  error: string | null;
  nodes: number;
  preview: string;
  created_at: string;
  ingested_at: string | null;
};

export type IngestionStatus = {
  site_key: string;
  document_count: number;
  counts: Record<string, number>;
  sources: Source[];
};

export type TourStop = { narration: string; move?: Record<string, unknown> | null; label?: string };
export type TourPlan = { site_key: string; stops: TourStop[]; exists: boolean };

export type CacheEntry = {
  id: string;
  question: string;
  answer_text: string;
  components: Record<string, unknown>[];
  actions: Record<string, unknown>[];
  persona: string | null;
  page: string | null;
  channel: string | null;
  hit_count: number;
  created_at: string;
};
export type CacheList = { total: number; limit: number; offset: number; items: CacheEntry[] };

export type AnalyticsSeriesRow = {
  bucket: string;
  asr_cost: number;
  tts_cost: number;
  fast_llm_cost: number;
  thinker_llm_cost: number;
  tool_cost: number;
  total_cost: number;
  turns: number;
  cached_turns: number;
  generated_turns: number;
  avg_latency_ms: number;
};
export type Analytics = {
  site_key: string;
  group_by: string;
  series: AnalyticsSeriesRow[];
  totals: AnalyticsSeriesRow & Record<string, number>;
  performance: {
    turns: number;
    avg_latency_ms: number;
    p50_latency_ms: number;
    p95_latency_ms: number;
    cache_hit_rate: number;
  };
  cache_split: {
    cached: { turns: number; cost: number };
    generated: { turns: number; cost: number };
  };
  pricing: Record<string, number>;
};

// ---- endpoint helpers ------------------------------------------------------
export const Api = {
  register: (email: string, password: string, name?: string) =>
    api<AuthResponse>("/auth/register", { method: "POST", auth: false, body: { email, password, name } }),
  login: (email: string, password: string) =>
    api<AuthResponse>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  me: () => api<Tenant>("/auth/me"),

  listWebsites: () => api<Website[]>("/tenant/websites"),
  createWebsite: (body: Partial<Website>) =>
    api<Website>("/tenant/websites", { method: "POST", body }),
  getWebsite: (id: string) => api<Website>(`/tenant/websites/${id}`),
  updateWebsite: (id: string, body: Partial<Website>) =>
    api<Website>(`/tenant/websites/${id}`, { method: "PATCH", body }),
  deleteWebsite: (id: string) =>
    api<void>(`/tenant/websites/${id}`, { method: "DELETE" }),
  rotateKey: (id: string) =>
    api<Website>(`/tenant/websites/${id}/rotate-key`, { method: "POST" }),

  getProfile: (id: string) => api<AgentProfile>(`/tenant/websites/${id}/profile`),
  updateProfile: (id: string, body: Partial<Omit<AgentProfile, "site_key">>) =>
    api<AgentProfile>(`/tenant/websites/${id}/profile`, { method: "PUT", body }),

  // Public checks used by the Install tab's "Test connection".
  readiness: () => api<Readiness>("/readyz", { auth: false }),
  widgetConfig: (key: string) =>
    api<WidgetConfig>(`/widget/config?key=${encodeURIComponent(key)}`, { auth: false }),

  ingestion: (id: string) => api<IngestionStatus>(`/tenant/websites/${id}/ingestion`),
  addSource: (id: string, body: { kind: string; name: string; content: string }) =>
    api<Source>(`/tenant/websites/${id}/sources`, { method: "POST", body }),
  uploadSource: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Source>(`/tenant/websites/${id}/sources/upload`, { method: "POST", form });
  },
  deleteSource: (id: string, sid: string) =>
    api<void>(`/tenant/websites/${id}/sources/${sid}`, { method: "DELETE" }),
  runIngestion: (id: string) =>
    api<{ status: string; pending?: number; nodes?: number }>(
      `/tenant/websites/${id}/ingestion/run`,
      { method: "POST" }
    ),

  getTour: (id: string) => api<TourPlan>(`/tenant/websites/${id}/tour`),
  saveTour: (id: string, stops: TourStop[]) =>
    api<TourPlan>(`/tenant/websites/${id}/tour`, { method: "PUT", body: { stops } }),
  generateTour: (id: string) =>
    api<TourPlan>(`/tenant/websites/${id}/tour/generate`, { method: "POST" }),

  listCache: (id: string, params: { limit?: number; offset?: number; search?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    if (params.search) q.set("search", params.search);
    const qs = q.toString();
    return api<CacheList>(`/tenant/websites/${id}/cache${qs ? `?${qs}` : ""}`);
  },
  updateCache: (id: string, eid: string, body: Partial<CacheEntry>) =>
    api<CacheEntry>(`/tenant/websites/${id}/cache/${eid}`, { method: "PUT", body }),
  deleteCache: (id: string, eid: string) =>
    api<void>(`/tenant/websites/${id}/cache/${eid}`, { method: "DELETE" }),

  analytics: (id: string, groupBy: "day" | "hour" | "session") =>
    api<Analytics>(`/tenant/websites/${id}/analytics?group_by=${groupBy}`),
};
