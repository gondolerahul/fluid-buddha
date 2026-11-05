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
export type Role = "owner" | "admin" | "editor" | "viewer";
export const ROLES: Role[] = ["viewer", "editor", "admin", "owner"];
export type User = { id: string; email: string; name: string | null };
/** The account you act in, with your role in it and who you are (M2-1). */
export type Tenant = { id: string; email: string; name: string | null; role?: Role; user?: User };
export type AuthResponse = { access_token: string; token_type: string; tenant: Tenant; role: Role; user: User };
export type Account = { id: string; name: string; role: Role };
export type Member = { id: string; email: string; name: string | null; role: Role; joined_at: string;
  last_login_at: string | null; has_password: boolean };
export type Invitation = { id: string; email: string; role: Role; invited_by: string | null;
  created_at: string; expires_at: string };
export type Team = { members: Member[]; invitations: Invitation[]; me: { id: string; role: Role } };
export type InvitationInfo = { account: string; email: string; role: Role; expires_at: string; has_user: boolean };
export type AuditEvent = { id: number; actor_email: string | null; action: string; target_type: string | null;
  target_id: string | null; details: Record<string, unknown>; ip: string | null; user_agent: string | null;
  request_id: string | null; at: string };
export type SSODomain = { domain: string; verified: boolean; txt_name: string; txt_value: string };
export type SSOConfig = { configured: boolean; issuer?: string; client_id?: string; has_secret?: boolean;
  default_role?: Exclude<Role, "owner">; require_sso?: boolean; enabled?: boolean; redirect_uri: string;
  domains: SSODomain[] };

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
  /** First words when opened; empty = a page-aware welcome (M2-4). */
  greeting?: string;
  default_persona?: string;
  tour_enabled?: boolean;
  /** Products visitors compare this one with (Insights counts mentions, M2-5). */
  competitors?: string[];
  /** The next step a recap page offers (M2-6). */
  cta_label?: string;
  cta_url?: string;
  /** Languages (M2-7): "en" always, plus "hi" when the agent may answer in
   *  Hindi; the widget's labels; the greeting for a visitor in Hindi. */
  languages?: ("en" | "hi")[];
  widget_language?: "auto" | "en" | "hi";
  greeting_hi?: string;
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

/** Insights v2 (M2-5). */
export type SignalExample = { question: string; at: string; conversation_id: string };
export type ObjectionStat = { type: string; label: string; count: number; previous: number; examples: SignalExample[] };
export type CompetitorStat = { name: string; count: number; previous: number; examples: SignalExample[] };
export type FeatureRequest = { text: string; count: number; last_at: string; examples: (SignalExample & { text: string })[] };
export type Signals = {
  days: number; classified: number; pending: number;
  objections: ObjectionStat[]; competitors: CompetitorStat[]; requests: FeatureRequest[];
  buying_signals: { turns: number; conversations: number };
  /** Questions by the language visitors wrote in (M2-7). */
  languages?: { lang: "en" | "hi" | "hinglish"; turns: number }[];
};
export type DigestSettings = {
  enabled: boolean; timezone: string; chosen: boolean; next_send: string; you: string;
  recipients: { email: string; unsubscribed: boolean }[];
};
export type DigestPreview = { subject: string; text: string; html: string };

/** Variant tests (M2-4). */
export type TestSubject = "greeting" | "trigger" | "tour" | "persona" | "design";
export type VariantOverrides = { greeting?: string; triggers?: string[]; tour?: boolean;
  persona?: string; design?: "level1" | "level2" | "level3" };
export type Variant = { key: string; label: string; overrides: VariantOverrides };
export type VariantTest = {
  id: string; name: string; subject: TestSubject; variants: Variant[];
  holdout_pct: number; goal_path: string | null; status: "running" | "stopped";
  started_at: string; ended_at: string | null; bots_ignored: number;
  winner: string | null; promoted_at: string | null; visitors?: number;
};
export type VariantResult = Variant & {
  visitors: number; converters: number; rate: number | null;
  /** This variant vs the control; null for the control itself. */
  vs_control: ExperimentResults["lift"] | null;
};
export type VariantTestResults = {
  experiment: VariantTest;
  variants: VariantResult[];
  verdict: { status: "winner" | "keep_running" | "no_difference"; winner: string | null; alpha: number };
  plan: { baseline: number; baseline_source: "given" | "observed" | "default"; mde: number;
    needed: { total: number; per_variant: number; holdout: number } | null;
    visitors_so_far: number; visitors_per_day: number | null; days_left: number | null; reached: boolean };
  /** All variants together vs the holdout, when the test keeps one. */
  holdout: ExperimentResults["lift"] | null;
};
export type VariantTestIn = { name: string; subject: TestSubject; holdout_pct: number;
  goal_path: string | null; variants: { label: string; overrides: VariantOverrides }[] };

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
  /** The language the answer was given in (M2-7). */
  lang?: "en" | "hi";
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
  /** The conversation's shared recap, if the visitor asked for one (M2-6). */
  recap?: { views: number; forwards: number; last_viewed_at: string | null } | null;
};
export type Recap = {
  id: string; url: string; conversation_id: string; created_at: string; updated_at: string;
  expires_at: string; expired: boolean; views: number; viewers: number; forwards: number;
  last_viewed_at: string | null; summary: string | null; lead_email: string | null;
};
export type Privacy = {
  redact_pii: boolean;
  consent_required: boolean;
  privacy_policy_url: string | null;
  /** 0 keeps data until deleted. */
  transcript_retention_days: number;
  lead_retention_days: number;
  /** How long a shared recap link works (M2-6). */
  recap_days?: number;
};
export type Integrations = {
  webhook_url: string | null;
  webhook_secret: string;
  slack_webhook_url: string | null;
  hot_lead_score: number;
  /** Alert when the site's AI cost for the day passes this (USD); null = off. */
  cost_alert_usd: number | null;
};
/** A per-site cost alert (F-3), raised at most once per kind per UTC day. */
export type CostAlert = {
  day: string;
  level: "threshold" | "cap_80" | "cap_100";
  spent_usd: number;
  limit_usd: number;
  delivered: boolean;
  error: string | null;
  at: string;
};

/** Live takeover (M2-2). */
export type LiveTakeover = { id?: string; operator_name: string; operator_user_id?: string | null; started_at?: string };
export type LiveSession = { site_key: string; session_id: string; channel: "voice" | "text";
  persona: string | null; page: string | null; started_at: string; last_seen: string;
  conversation_id: string | null; turns: number; last_question: string | null; lead_score: number | null;
  hot: boolean; takeover: LiveTakeover | null; website_id: string; website_name: string };
export type LiveLine = { id?: number; sender: "visitor" | "agent" | "operator" | "system";
  author?: string | null; text: string; at: string };
export type LiveConversation = { session_id: string; live: boolean; takeover: LiveTakeover | null;
  events: LiveLine[] };
export type IceServer = { urls: string | string[]; username?: string; credential?: string };

/** Proactive triggers (M2-3). */
export type TriggerKind = "time_on_page" | "scroll_depth" | "exit_intent" | "return_visit";
export type TriggerRuleIn = { name: string; enabled: boolean; kind: TriggerKind; seconds?: number | null;
  percent?: number | null; visits?: number | null; within_days?: number | null; pages: string[];
  message: string; action: "nudge" | "open"; max_per_day: number; priority: number };
export type TriggerStats = { shown: number; clicked: number; dismissed: number; engaged: number;
  click_rate: number | null; engage_rate: number | null };
export type TriggerRule = TriggerRuleIn & { id: string; updated_at: string; stats: TriggerStats | null };

// ---- endpoint helpers ------------------------------------------------------
export const Api = {
  register: (email: string, password: string, name?: string) =>
    api<AuthResponse>("/auth/register", { method: "POST", auth: false, body: { email, password, name } }),
  login: (email: string, password: string) =>
    api<AuthResponse>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  me: () => api<Tenant>("/auth/me"),
  accounts: () => api<Account[]>("/auth/accounts"),
  switchAccount: (tenant_id: string) =>
    api<AuthResponse>("/auth/switch", { method: "POST", body: { tenant_id } }),
  invitation: (token: string) =>
    api<InvitationInfo>(`/auth/invitations/${encodeURIComponent(token)}`, { auth: false }),
  acceptInvitation: (token: string, body: { name?: string; password?: string }, signedIn: boolean) =>
    api<AuthResponse>(`/auth/invitations/${encodeURIComponent(token)}/accept`,
      { method: "POST", body, auth: signedIn }),
  ssoStart: (provider: "google" | "oidc", email?: string) =>
    api<{ url: string }>("/auth/sso/start", { method: "POST", auth: false, body: { provider, email } }),

  live: () => api<LiveSession[]>("/tenant/live"),
  liveIce: () => api<{ ice_servers: IceServer[] }>("/tenant/live/ice"),
  liveConversation: (wid: string, sid: string) =>
    api<LiveConversation>(`/tenant/websites/${wid}/live/${sid}`),
  takeOver: (wid: string, sid: string) =>
    api<LiveTakeover>(`/tenant/websites/${wid}/live/${sid}/takeover`, { method: "POST" }),
  sendLive: (wid: string, sid: string, text: string) =>
    api<LiveLine>(`/tenant/websites/${wid}/live/${sid}/message`, { method: "POST", body: { text } }),
  releaseLive: (wid: string, sid: string) =>
    api<{ released: boolean }>(`/tenant/websites/${wid}/live/${sid}/release`, { method: "POST" }),
  callSignal: (wid: string, sid: string, body: { type: "offer" | "ice" | "hangup"; sdp?: string;
    candidate?: RTCIceCandidateInit }) =>
    api<{ sent: boolean }>(`/tenant/websites/${wid}/live/${sid}/call`, { method: "POST", body }),

  signals: (wid: string, days = 30) => api<Signals>(`/tenant/websites/${wid}/insights/signals?days=${days}`),
  sendRequest: (wid: string, body: { channel: "slack" | "webhook" | "email"; text: string; count: number;
    examples: string[]; email?: string }) =>
    api<{ sent: boolean }>(`/tenant/websites/${wid}/insights/requests/send`, { method: "POST", body }),
  digest: () => api<DigestSettings>("/tenant/digest"),
  saveDigest: (body: { enabled: boolean; recipients: string[]; timezone: string }) =>
    api<DigestSettings>("/tenant/digest", { method: "PUT", body }),
  previewDigest: () => api<DigestPreview>("/tenant/digest/preview"),
  sendTestDigest: () => api<{ queued: number; to: string }>("/tenant/digest/send-test", { method: "POST" }),
  tests: (wid: string) =>
    api<{ tests: VariantTest[]; holdout_running: boolean }>(`/tenant/websites/${wid}/tests`),
  startTest: (wid: string, body: VariantTestIn) =>
    api<VariantTest>(`/tenant/websites/${wid}/tests`, { method: "POST", body }),
  testResults: (wid: string, tid: string) =>
    api<VariantTestResults>(`/tenant/websites/${wid}/tests/${tid}`),
  planTest: (wid: string, q: { variants: number; baseline: number; mde: number; holdout_pct: number }) =>
    api<{ needed: { total: number; per_variant: number; holdout: number } | null }>(
      `/tenant/websites/${wid}/tests/plan?${new URLSearchParams(Object.entries(q).map(([k, v]) => [k, String(v)]))}`),
  stopTest: (wid: string, tid: string) =>
    api<VariantTest>(`/tenant/websites/${wid}/tests/${tid}/stop`, { method: "POST" }),
  promoteVariant: (wid: string, tid: string, variant: string) =>
    api<VariantTest>(`/tenant/websites/${wid}/tests/${tid}/promote`, { method: "POST", body: { variant } }),
  triggers: (wid: string) => api<{ rules: TriggerRule[] }>(`/tenant/websites/${wid}/triggers`),
  createTrigger: (wid: string, body: TriggerRuleIn) =>
    api<TriggerRule>(`/tenant/websites/${wid}/triggers`, { method: "POST", body }),
  updateTrigger: (wid: string, id: string, body: TriggerRuleIn) =>
    api<TriggerRule>(`/tenant/websites/${wid}/triggers/${id}`, { method: "PUT", body }),
  deleteTrigger: (wid: string, id: string) =>
    api<void>(`/tenant/websites/${wid}/triggers/${id}`, { method: "DELETE" }),

  team: () => api<Team>("/tenant/team"),
  invite: (email: string, role: Role) =>
    api<{ id: string; link: string; emailed: boolean }>("/tenant/team/invitations",
      { method: "POST", body: { email, role } }),
  revokeInvitation: (id: string) => api<void>(`/tenant/team/invitations/${id}`, { method: "DELETE" }),
  changeRole: (userId: string, role: Role) =>
    api<{ role: Role }>(`/tenant/team/members/${userId}`, { method: "PATCH", body: { role } }),
  removeMember: (userId: string) => api<void>(`/tenant/team/members/${userId}`, { method: "DELETE" }),
  audit: (q: { before?: number; action?: string; actor?: string }) => {
    const p = new URLSearchParams();
    if (q.before) p.set("before", String(q.before));
    if (q.action) p.set("action", q.action);
    if (q.actor) p.set("actor", q.actor);
    return api<AuditEvent[]>(`/tenant/audit?${p}`);
  },
  auditCsv: async (): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/tenant/audit.csv`, {
      headers: { Authorization: `Bearer ${getToken() ?? ""}` },
    });
    if (!res.ok) throw new ApiError(res.status, "Could not export the audit log");
    return res.blob();
  },
  ssoConfig: () => api<SSOConfig>("/tenant/sso"),
  saveSSO: (body: { issuer: string; client_id: string; client_secret?: string;
    default_role: string; require_sso: boolean; enabled: boolean }) =>
    api<SSOConfig>("/tenant/sso", { method: "PUT", body }),
  deleteSSO: () => api<void>("/tenant/sso", { method: "DELETE" }),
  addSSODomain: (domain: string) =>
    api<SSODomain>("/tenant/sso/domains", { method: "POST", body: { domain } }),
  verifySSODomain: (domain: string) =>
    api<{ verified: boolean }>(`/tenant/sso/domains/${encodeURIComponent(domain)}/verify`, { method: "POST" }),
  deleteSSODomain: (domain: string) =>
    api<void>(`/tenant/sso/domains/${encodeURIComponent(domain)}`, { method: "DELETE" }),

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
    hot_lead_score: number; cost_alert_usd: number | null; rotate_secret?: boolean;
  }) => api<Integrations>(`/tenant/websites/${id}/integrations`, { method: "PUT", body }),
  costAlerts: (id: string, days = 7) =>
    api<CostAlert[]>(`/tenant/websites/${id}/cost-alerts?days=${days}`),
  testIntegrations: (id: string) =>
    api<{ ok: boolean; error: string | null }>(`/tenant/websites/${id}/integrations/test`,
      { method: "POST" }),

  recaps: (id: string) => api<{ recaps: Recap[] }>(`/tenant/websites/${id}/recaps`),
  revokeRecap: (id: string, rid: string) =>
    api<void>(`/tenant/websites/${id}/recaps/${rid}`, { method: "DELETE" }),
  getPrivacy: (id: string) => api<Privacy>(`/tenant/websites/${id}/privacy`),
  savePrivacy: (id: string, body: Privacy) =>
    api<Privacy>(`/tenant/websites/${id}/privacy`, { method: "PUT", body }),
  eraseVisitor: (id: string, email: string) =>
    api<{ leads: number; conversations: number }>(`/tenant/websites/${id}/privacy/erase`,
      { method: "POST", body: { email } }),
};
