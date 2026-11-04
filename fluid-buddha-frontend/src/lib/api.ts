/**
 * Typed client for the FluidBuddha backend admin API. Attaches the JWT bearer
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

/** One "crawl my website" run (WS9). */
export type CrawlJob = {
  id: string;
  start_url: string;
  max_pages: number;
  max_depth: number;
  status: "running" | "done" | "failed";
  phase: "crawling" | "ingesting" | "personas" | "design" | "done";
  pages_found: number;
  pages_ingested: number;
  pages_skipped: number;
  personas_added: number;
  design_found: boolean;
  error: string | null;
  started_at: string;
  finished_at: string | null;
  /** Paste-URL → live, in seconds. */
  duration_s: number | null;
};
export type DesignInfo = {
  /** Tokens read off the site; null before a crawl. */
  extracted: { name?: string; logo_url?: string; colors?: Record<string, string>;
    typography?: Record<string, string>; radius?: string } | null;
  design: Record<string, unknown>;
};

/** Billing with Razorpay (WS12). Amounts are in the currency's minor unit. */
export type BillingPlan = {
  key: string;
  name: string;
  price: number;
  included: number | null;
  overage: number | null;
  self_serve: boolean;
};
export type BillingSummary = {
  plan: string;
  subscribed_plan: string;
  pending_plan: string | null;
  status: string;
  /** A switch at the next renewal (UPI Autopay can't change plans in place):
   *  created = mandate still to approve; authenticated = approved. */
  next: { plan: string; status: string; starts_at: string | null } | null;
  cancel_at_cycle_end: boolean;
  currency: string;
  period: { start: string; end: string };
  usage: { conversations: number; included: number | null; extra: number;
    overage_amount: number; capped: boolean; limit_reached: boolean };
  sites: Array<{ website_id: string; name: string; conversations: number; turns: number;
    cost_usd: number; cost_per_conversation_usd: number | null }>;
  overage_history: Array<{ period_start: string; period_end: string; plan: string;
    conversations: number; extra: number; amount: number; currency: string; addon_id: string | null;
    /** addon: on the next invoice; link: payment link sent (UPI autopay can't take add-ons). */
    status: "pending" | "addon" | "link" | "paid" | "nothing"; payment_link_url: string | null }>;
  catalog: BillingPlan[];
  checkout_enabled: boolean;
  key_id: string | null;
};
export type CheckoutResult =
  | { action: "checkout"; plan: string; subscription_id: string; short_url: string | null;
      key_id: string; email: string; name: string;
      /** Set when the plan starts at the next renewal (UPI Autopay). */
      scheduled_for?: string | null }
  | { action: "changed"; plan: string; effective: "now" | "cycle_end" };

/** Holdout A/B (WS11). */
export type ExperimentSettings = {
  id: string | null;
  enabled: boolean;
  holdout_pct: number;
  goal_path: string | null;
  status: "running" | "stopped" | null;
  started_at: string | null;
  ended_at: string | null;
  /** Automated visits (crawlers, headless browsers) turned away from this run. */
  bots_ignored: number;
  started_new_run?: boolean;
};
export type LiftArm = {
  visitors: number;
  converters: number;
  rate: number;
  rate_low: number;
  rate_high: number;
};
export type ExperimentResults = {
  experiment: ExperimentSettings;
  lift: {
    /** significant: the always-valid interval excludes 0. trending: only the
     *  fixed-horizon one does — promising, keep the test running. */
    status: "collecting" | "significant" | "trending" | "not_significant";
    agent: LiftArm;
    holdout: LiftArm;
    /** agent − holdout, as a rate (0.012 = 1.2 points) */
    diff: number | null;
    diff_low: number | null;
    diff_high: number | null;
    relative: number | null;
    relative_low: number | null;
    relative_high: number | null;
    p_value: number | null;
    /** Always-valid (mSPRT) interval and p-value: safe to read at any time. */
    seq_low: number | null;
    seq_high: number | null;
    seq_p_value: number | null;
  };
  series: Array<{ day: string; agent_rate: number | null; holdout_rate: number | null;
    agent_visitors: number; holdout_visitors: number }>;
  goals: Array<{ name: string; arm: "agent" | "holdout"; events: number }>;
};
export type ExperimentPlan = {
  baseline: number;
  baseline_source: "given" | "observed" | "default";
  observed_baseline: number | null;
  /** relative lift to detect: 0.2 = +20 % */
  mde: number;
  holdout_pct: number;
  needed: { total: number; holdout: number; agent: number } | null;
  visitors_so_far: number;
  visitors_per_day: number | null;
  days_left: number | null;
  reached: boolean;
};

export type TourStop = { narration: string; move?: Record<string, unknown> | null; label?: string };
export type TourPlan = { site_key: string; stops: TourStop[]; exists: boolean; edited: boolean };

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
  status: CacheStatus;
  created_at: string;
};
/** auto: replayed by similarity; pinned: always replayed; blocked: never replayed. */
export type CacheStatus = "auto" | "pinned" | "blocked";
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
    /** Time to first audio (question in → first speech out), over spoken voice turns. */
    ttfa_turns: number;
    p50_ttfa_ms: number | null;
    p95_ttfa_ms: number | null;
    conversations: number;
    cost_per_conversation: number | null;
  };
  cache_split: {
    cached: { turns: number; cost: number };
    generated: { turns: number; cost: number };
  };
  pricing: Record<string, number>;
};

export type QuestionStat = {
  question: string;
  count: number;
  last_asked: string | null;
  best_confidence: number;
};
export type Insights = {
  days: number;
  conversations: number;
  engaged: number;
  turns: number;
  grounded_rate: number | null;
  top_questions: QuestionStat[];
  gaps: QuestionStat[];
  funnel: { stage: string; label: string; count: number }[];
};
export type ConversationSummary = {
  id: string;
  channel: string;
  persona: string | null;
  first_page: string | null;
  turns: number;
  ungrounded: number;
  first_question: string | null;
  started_at: string;
  last_at: string;
};
export type ConversationTurn = {
  question: string;
  answer: string;
  intent: string | null;
  persona: string | null;
  page: string | null;
  found: boolean;
  confidence: number;
  sources: { label?: string; route?: string; document?: string }[];
  served_from_cache: boolean;
  /** A real question the content didn't cover (small talk never counts). */
  unanswered: boolean;
  at: string;
};
export type Conversation = ConversationSummary & { transcript: ConversationTurn[] };

export type LeadStatus = "new" | "contacted" | "qualified" | "won" | "lost";
export type Lead = {
  id: string;
  source: "form" | "conversation" | string;
  name: string | null;
  email: string;
  company: string | null;
  phone: string | null;
  message: string | null;
  interest: string | null;
  persona: string | null;
  score: number;
  summary: string;
  status: LeadStatus;
  conversation_id: string | null;
  delivered_at: string | null;
  delivery_error: string | null;
  created_at: string;
};
export type Privacy = {
  redact_pii: boolean;
  consent_required: boolean;
  privacy_policy_url: string | null;
  /** 0 keeps data until deleted. */
  transcript_retention_days: number;
  lead_retention_days: number;
};
export type Integrations = {
  webhook_url: string | null;
  webhook_secret: string;
  slack_webhook_url: string | null;
  hot_lead_score: number;
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
  startCrawl: (id: string, body: { url?: string; max_pages: number; max_depth: number }) =>
    api<CrawlJob>(`/tenant/websites/${id}/crawl`, { method: "POST", body }),
  latestCrawl: (id: string) => api<CrawlJob | null>(`/tenant/websites/${id}/crawl`),
  getDesign: (id: string) => api<DesignInfo>(`/tenant/websites/${id}/design`),
  runIngestion: (id: string) =>
    api<{ status: string; pending?: number; nodes?: number }>(
      `/tenant/websites/${id}/ingestion/run`,
      { method: "POST" }
    ),

  billing: () => api<BillingSummary>("/tenant/billing"),
  checkout: (plan: string) =>
    api<CheckoutResult>("/tenant/billing/checkout", { method: "POST", body: { plan } }),
  verifyPayment: (body: { razorpay_payment_id: string; razorpay_subscription_id: string;
    razorpay_signature: string }) =>
    api<BillingSummary>("/tenant/billing/verify", { method: "POST", body }),
  cancelSubscription: () => api<BillingSummary>("/tenant/billing/cancel", { method: "POST" }),

  getExperiment: (id: string) => api<ExperimentSettings>(`/tenant/websites/${id}/experiment`),
  saveExperiment: (id: string, body: { enabled: boolean; holdout_pct: number; goal_path: string | null }) =>
    api<ExperimentSettings>(`/tenant/websites/${id}/experiment`, { method: "PUT", body }),
  restartExperiment: (id: string) =>
    api<ExperimentSettings>(`/tenant/websites/${id}/experiment/restart`, { method: "POST" }),
  experimentResults: (id: string) =>
    api<ExperimentResults | null>(`/tenant/websites/${id}/experiment/results`),
  experimentPlan: (id: string, q: { baseline?: number; mde: number; holdout_pct?: number }) => {
    const p = new URLSearchParams({ mde: String(q.mde) });
    if (q.baseline != null) p.set("baseline", String(q.baseline));
    if (q.holdout_pct != null) p.set("holdout_pct", String(q.holdout_pct));
    return api<ExperimentPlan>(`/tenant/websites/${id}/experiment/plan?${p}`);
  },

  getTour: (id: string) => api<TourPlan>(`/tenant/websites/${id}/tour`),
  saveTour: (id: string, stops: TourStop[]) =>
    api<TourPlan>(`/tenant/websites/${id}/tour`, { method: "PUT", body: { stops } }),
  generateTour: (id: string) =>
    api<TourPlan>(`/tenant/websites/${id}/tour/generate`, { method: "POST" }),

  listCache: (id: string, params: {
    limit?: number; offset?: number; search?: string; status?: CacheStatus;
  } = {}) => {
    const q = new URLSearchParams();
    if (params.status) q.set("status_filter", params.status);
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

  insights: (id: string, days = 30) =>
    api<Insights>(`/tenant/websites/${id}/insights?days=${days}`),
  conversations: (id: string, offset = 0, limit = 25) =>
    api<{ items: ConversationSummary[]; total: number; limit: number; offset: number }>(
      `/tenant/websites/${id}/conversations?limit=${limit}&offset=${offset}`),
  conversation: (id: string, cid: string) =>
    api<Conversation>(`/tenant/websites/${id}/conversations/${cid}`),

  leads: (id: string, offset = 0, limit = 50) =>
    api<{ items: Lead[]; total: number; limit: number; offset: number }>(
      `/tenant/websites/${id}/leads?limit=${limit}&offset=${offset}`),
  updateLead: (id: string, lid: string, status: LeadStatus) =>
    api<Lead>(`/tenant/websites/${id}/leads/${lid}`, { method: "PATCH", body: { status } }),
  getIntegrations: (id: string) => api<Integrations>(`/tenant/websites/${id}/integrations`),
  saveIntegrations: (id: string, body: {
    webhook_url: string | null; slack_webhook_url: string | null;
    hot_lead_score: number; rotate_secret?: boolean;
  }) => api<Integrations>(`/tenant/websites/${id}/integrations`, { method: "PUT", body }),
  testIntegrations: (id: string) =>
    api<{ ok: boolean; error: string | null }>(`/tenant/websites/${id}/integrations/test`,
      { method: "POST" }),

  getPrivacy: (id: string) => api<Privacy>(`/tenant/websites/${id}/privacy`),
  savePrivacy: (id: string, body: Privacy) =>
    api<Privacy>(`/tenant/websites/${id}/privacy`, { method: "PUT", body }),
  eraseVisitor: (id: string, email: string) =>
    api<{ leads: number; conversations: number }>(`/tenant/websites/${id}/privacy/erase`,
      { method: "POST", body: { email } }),
};
