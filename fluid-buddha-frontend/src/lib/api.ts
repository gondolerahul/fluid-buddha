/**
 * Typed client for the FluidBuddha backend admin API.
 *
 * Signed-in state is an httpOnly session cookie set by the backend (M2-11):
 * page scripts never see the token. Every request goes with credentials, and
 * a request that changes something carries the session's CSRF token, which
 * the backend hands back at sign-in and from /auth/me. Non-2xx answers throw
 * a friendly ApiError; an ended session or a pending two-factor setup is
 * announced on window so the app can react in one place.
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

// Before M2-11 the console kept a bearer token in localStorage; drop it.
const LEGACY_TOKEN_KEY = "fb_token";
export function clearLegacyToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(LEGACY_TOKEN_KEY);
}

let csrfToken: string | null = null;
/** The session's CSRF token (from sign-in or /auth/me); kept in memory only. */
export function setCsrf(token: string | null | undefined) {
  csrfToken = token ?? null;
}
export function getCsrf(): string | null {
  return csrfToken;
}

/** Fired on window when the backend says the session ended (idle, expired,
 *  revoked) or that this account requires two-factor first. */
export const SESSION_ENDED = "fb:session-ended";
export const MFA_REQUIRED = "fb:mfa-required";

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

/** fetch() against the backend with the session cookie and, for changes, the
 *  CSRF token. */
export function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  return fetch(`${API_BASE}${path}`, { ...init, method, headers, credentials: "include" });
}

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, auth = true, form } = opts;
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await backendFetch(path, { method, headers, body: payload });
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const message = errorMessage(data, res.statusText);
    if (auth && typeof window !== "undefined") {
      if (res.status === 401) window.dispatchEvent(new Event(SESSION_ENDED));
      if (res.status === 403 && message === "mfa_setup_required") window.dispatchEvent(new Event(MFA_REQUIRED));
    }
    throw new ApiError(res.status, message === "csrf_failed"
      ? "Your session needs refreshing. Reload the page and try again." : message);
  }
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
  if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
    // {message, problems[]} (e.g. a manifest that can't be approved yet).
    const d = detail as { message?: unknown; problems?: unknown };
    const problems = Array.isArray(d.problems) ? d.problems.map(String) : [];
    return [String(d.message ?? ""), ...problems].filter(Boolean).join(" · ");
  }
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
export type Security = { mfa_enabled: boolean; mfa_required: boolean; session_mfa: boolean;
  mfa_setup_required: boolean; idle_minutes: number };
export type Tenant = { id: string; email: string; name: string | null; role?: Role; user?: User;
  csrf_token?: string | null; security?: Security };
export type AuthResponse = { access_token: string; token_type: string; tenant: Tenant; role: Role; user: User;
  csrf_token?: string | null; expires_at?: string | null };
/** The site's agent endpoint for AI assistants (M3-2). */
export type AgentToken = { id: string; name: string; scopes: string[]; created_at: string; last_used_at: string | null };
export type AgentAccess = {
  enabled: boolean;
  endpoints: { mcp: string; llms_txt: string; openapi: string; ask: string } | null;
  tokens: AgentToken[];
  traffic: { days: number; total: number; by_tool: { tool: string; count: number; failed: number }[];
    by_client: { client: string; count: number }[];
    recent: { kind: string; tool: string | null; client: string | null; ok: boolean; error: string | null; at: string }[] };
};
/** Self-hosted licence (M3-5). */
export type LicenceState = {
  self_hosted: boolean;
  state?: "valid" | "expiring" | "grace" | "expired" | "missing" | "invalid";
  usable?: boolean; reason?: string; source?: "console" | "env" | "file" | null;
  days_left?: number; grace_until?: string;
  licence?: { lid: string; customer: string; sites: number; seats: number; features: string[];
    issued_at: string; expires_at: string; grace_days: number };
  usage?: { sites: number; seats: number };
};
/** Generative landing pages (M3-1). */
export type CampaignStatus = "draft" | "live" | "paused";
export type Testimonial = { quote: string; name: string; role?: string };
export type CampaignLogo = { src: string; alt: string };
export type CampaignVariant = { headline?: string; key_messages?: string[]; cta_label?: string };
export type CampaignIn = {
  name: string; slug?: string; status: CampaignStatus; goal: string; audience: string; persona: string | null;
  key_messages: string[]; sections: string[]; cta_label: string; cta_url: string;
  testimonials: Testimonial[]; logos: CampaignLogo[]; variant: CampaignVariant | null; embed_origins: string[];
};
export type Campaign = CampaignIn & {
  id: string; slug: string; version: number; created_at: string; updated_at: string;
  url: string; preview_url: string; embed_snippet: string; embed_note: string;
  views_30d?: number; conversions_30d?: number;
};
export type CampaignList = {
  campaigns: Campaign[]; personas: { slug: string; label: string }[];
  sections: { type: string; label: string }[]; default_sections: string[];
};
export type CampaignCounts = { views: number; engaged: number; converted: number; conversion_rate: number };
export type CampaignAnalytics = {
  days: number; total: CampaignCounts;
  by_arm: (CampaignCounts & { arm: string })[];
  by_persona: (CampaignCounts & { persona: string | null })[];
  by_source: (CampaignCounts & { source: string | null })[];
  daily: { day: string; views: number; converted: number }[];
  cache: { pages: number; hits: number; avg_build_ms: number; served_from_cache: number; page_views: number; hit_rate: number };
  experiment?: { status: "winner" | "no_difference" | "keep_running"; winner: string | null };
};
/** Bring your own model (M3-4). */
export type ModelProviderKind = "anthropic" | "openai" | "azure_openai";
export type ModelPrice = { in?: number | null; out?: number | null };
export type ModelProvider = {
  configured: boolean; provider?: ModelProviderKind; fast_model?: string; thinker_model?: string;
  endpoint?: string | null; api_version?: string | null; prices?: { fast?: ModelPrice; thinker?: ModelPrice };
  enabled?: boolean; key_hint?: string; last_test_at?: string | null; last_test_ok?: boolean | null;
  last_error?: string | null;
  defaults: Record<ModelProviderKind, { fast_model: string; thinker_model: string }>;
  list_prices: Record<string, { in: number; out: number }>;
  sites: { id: string; name: string; byo_model: boolean }[];
};
export type ModelProviderIn = {
  provider: ModelProviderKind; fast_model: string; thinker_model: string; api_key?: string;
  endpoint?: string | null; api_version?: string | null;
  prices?: { fast?: ModelPrice; thinker?: ModelPrice }; enabled: boolean;
};
export type MFAChallenge = { mfa_required: true; mfa_token: string };
export type MFAStatus = { enabled: boolean; enabled_at: string | null; required: boolean; recovery_codes_left: number };
export type SessionInfo = { id: string; method: string; created_at: string; last_seen_at: string;
  ip: string | null; user_agent: string | null; account: string };
export type AccountSecurity = { require_mfa: boolean; members_without_mfa: string[]; session_idle_minutes: number;
  session_absolute_hours: number; login_max_attempts: number; login_lockout_minutes: number };
export type Account = { id: string; name: string; role: Role };
export type Member = { id: string; email: string; name: string | null; role: Role; joined_at: string;
  last_login_at: string | null; has_password: boolean; mfa_enabled?: boolean };
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
  /** From a vertical template (M2-9), editable. */
  starter_questions?: string[];
  starter_questions_hi?: string[];
  /** Money in calculators and configurators (ISO 4217, default INR). */
  currency?: string;
  guardrails?: string[];
  preferred_components?: string[];
  lead_fields?: string[];
  tour_outline?: string[];
  safety?: "" | "medical";
  template?: { id?: string; applied_at?: string };
};
/** Vertical templates (M2-9). */
export type TemplateSummary = {
  id: string; name: string; description: string; personas: string[];
  suggested_actions: { kind: string; label: string; why: string }[];
};
export type TemplatePlan = {
  template: string;
  set: { field: string; label: string; value: unknown }[];
  kept: { field: string; label: string }[];
  personas_added: { slug: string; label: string }[];
  triggers_added: string[];
  suggested_actions: { kind: string; label: string; why: string }[];
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
export type TestSubject = "greeting" | "trigger" | "tour" | "persona" | "design" | "regions" | "freeform";
export type VariantOverrides = { greeting?: string; triggers?: string[]; tour?: boolean;
  persona?: string; design?: "level1" | "level2" | "level3"; regions?: boolean; freeform?: boolean };
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
  /** Paid through a payment action (M2-8); paise. */
  paid_at?: string | null;
  paid_amount?: number | null;
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
  /** Remember returning visitors who opt in (M3-3), kept this long after their last visit. */
  memory_enabled?: boolean;
  memory_days?: number;
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
  message: string; compose?: boolean; action: "nudge" | "open"; max_per_day: number; priority: number };
export type TriggerStats = { shown: number; clicked: number; dismissed: number; engaged: number;
  click_rate: number | null; engage_rate: number | null };
export type TriggerRule = TriggerRuleIn & { id: string; updated_at: string; stats: TriggerStats | null };

// ---- endpoint helpers ------------------------------------------------------
/** Actions marketplace (M2-8). */
export type ActionKind = "payment_link" | "quote_request" | "trial" | "meeting_link" | "webhook";
export type ActionField = {
  key: string; label: string; type: "text" | "email" | "number" | "integer" | "boolean" | "choice";
  required: boolean; options?: string[]; max?: number;
};
export type Price = { key: string; label: string; amount: number; currency?: string };
export type ActionConfig = {
  max_per_hour?: number; key_id?: string; prices?: Price[]; url?: string;
  booking_url?: string; style?: "calendly" | "cal" | "plain"; fields?: ActionField[];
};
export type SiteAction = {
  id: string; kind: ActionKind; name: string; label: string; description: string; enabled: boolean;
  config: ActionConfig; has_secret: boolean; fields: ActionField[]; razorpay_webhook_url?: string;
};
export type ActionIn = {
  kind?: ActionKind; name: string; label: string; description: string; enabled: boolean;
  config: ActionConfig; secrets?: { key_secret?: string; webhook_secret?: string };
};
export type ActionRun = {
  id: string; action_name: string; kind: ActionKind; session_id: string;
  status: "proposed" | "cancelled" | "expired" | "done" | "failed" | "paid";
  inputs: Record<string, unknown>; summary: { label: string; value: string }[];
  amount: number | null; currency: string | null; result: { url?: string; message?: string };
  error: string | null; lead_id: string | null; created_at: string; confirmed_at: string | null;
  finished_at: string | null; paid_at: string | null;
};
export type CustomComponentIn = {
  name: string; label: string; description: string; kind: "template" | "iframe";
  props_schema: Record<string, unknown>; template: { base: string; state: Record<string, unknown> } | null;
  iframe_url: string | null; enabled: boolean;
};
export type CustomComponent = CustomComponentIn & { id: string };

export const Api = {
  register: (email: string, password: string, name?: string) =>
    api<AuthResponse>("/auth/register", { method: "POST", auth: false, body: { email, password, name } }),
  login: (email: string, password: string) =>
    api<AuthResponse | MFAChallenge>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  loginMfa: (mfa_token: string, code: { code?: string; recovery_code?: string }) =>
    api<AuthResponse>("/auth/login/mfa", { method: "POST", auth: false, body: { mfa_token, ...code } }),
  logout: () => api<void>("/auth/logout", { method: "POST", auth: false }),
  me: () => api<Tenant>("/auth/me", { auth: false }),
  sessions: () => api<{ current: string; sessions: SessionInfo[] }>("/auth/sessions"),
  endSession: (id: string) => api<void>(`/auth/sessions/${id}`, { method: "DELETE" }),
  endOtherSessions: () => api<{ ended: number }>("/auth/sessions/revoke-others", { method: "POST" }),
  changePassword: (current_password: string, new_password: string) =>
    api<{ changed: boolean; other_sessions_ended: number }>("/auth/password",
      { method: "POST", body: { current_password, new_password } }),
  mfaStatus: () => api<MFAStatus>("/auth/mfa"),
  mfaSetup: () => api<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" }),
  mfaEnable: (code: string) =>
    api<{ enabled: boolean; recovery_codes: string[] }>("/auth/mfa/enable", { method: "POST", body: { code } }),
  mfaDisable: (code: string, password: string) =>
    api<{ enabled: boolean }>("/auth/mfa/disable", { method: "POST", body: { code, password } }),
  mfaRecoveryCodes: (code: string) =>
    api<{ recovery_codes: string[] }>("/auth/mfa/recovery-codes", { method: "POST", body: { code } }),
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
  actions: (wid: string) => api<{ actions: SiteAction[] }>(`/tenant/websites/${wid}/actions`),
  createAction: (wid: string, body: ActionIn) =>
    api<SiteAction>(`/tenant/websites/${wid}/actions`, { method: "POST", body }),
  updateAction: (wid: string, id: string, body: ActionIn) =>
    api<SiteAction>(`/tenant/websites/${wid}/actions/${id}`, { method: "PUT", body }),
  deleteAction: (wid: string, id: string) =>
    api<void>(`/tenant/websites/${wid}/actions/${id}`, { method: "DELETE" }),
  actionSecret: (wid: string, id: string) =>
    api<{ signing_secret: string | null; razorpay_webhook_url: string | null; has_razorpay_webhook_secret: boolean }>(
      `/tenant/websites/${wid}/actions/${id}/secret`),
  actionRuns: (wid: string) => api<{ runs: ActionRun[] }>(`/tenant/websites/${wid}/action-runs`),
  components: (wid: string) => api<{ components: CustomComponent[] }>(`/tenant/websites/${wid}/components`),
  createComponent: (wid: string, body: CustomComponentIn) =>
    api<CustomComponent>(`/tenant/websites/${wid}/components`, { method: "POST", body }),
  updateComponent: (wid: string, id: string, body: CustomComponentIn) =>
    api<CustomComponent>(`/tenant/websites/${wid}/components/${id}`, { method: "PUT", body }),
  deleteComponent: (wid: string, id: string) =>
    api<void>(`/tenant/websites/${wid}/components/${id}`, { method: "DELETE" }),
  previewComponent: (wid: string, spec: CustomComponentIn, props: Record<string, unknown>) =>
    api<{ component_type: string; initial_state: Record<string, unknown> }>(
      `/tenant/websites/${wid}/components/preview`, { method: "POST", body: { spec, props } }),

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
  quotePdf: async (wid: string, runId: string): Promise<Blob> => {
    const res = await backendFetch(`/tenant/websites/${wid}/action-runs/${runId}/quote.pdf`);
    if (!res.ok) throw new ApiError(res.status, "Could not download the quote");
    return res.blob();
  },
  auditCsv: async (): Promise<Blob> => {
    const res = await backendFetch("/tenant/audit.csv");
    if (!res.ok) throw new ApiError(res.status, "Could not export the audit log");
    return res.blob();
  },
  accessReviewCsv: async (): Promise<Blob> => {
    const res = await backendFetch("/tenant/team/access-review.csv");
    if (!res.ok) throw new ApiError(res.status, "Could not export the access review");
    return res.blob();
  },
  agentAccess: (wid: string) => api<AgentAccess>(`/tenant/websites/${wid}/agent-access`),
  setAgentAccess: (wid: string, enabled: boolean) =>
    api<{ enabled: boolean }>(`/tenant/websites/${wid}/agent-access`, { method: "PUT", body: { enabled } }),
  createAgentToken: (wid: string, name: string, scopes: string[]) =>
    api<AgentToken & { token: string }>(`/tenant/websites/${wid}/agent-tokens`, { method: "POST", body: { name, scopes } }),
  revokeAgentToken: (wid: string, id: string) =>
    api<void>(`/tenant/websites/${wid}/agent-tokens/${id}`, { method: "DELETE" }),
  licence: () => api<LicenceState>("/tenant/licence"),
  installLicence: (key: string) => api<LicenceState>("/tenant/licence", { method: "PUT", body: { key } }),
  campaigns: (wid: string) => api<CampaignList>(`/tenant/websites/${wid}/campaigns`),
  createCampaign: (wid: string, body: CampaignIn) =>
    api<Campaign>(`/tenant/websites/${wid}/campaigns`, { method: "POST", body }),
  saveCampaign: (wid: string, cid: string, body: CampaignIn) =>
    api<Campaign>(`/tenant/websites/${wid}/campaigns/${cid}`, { method: "PUT", body }),
  deleteCampaign: (wid: string, cid: string) =>
    api<void>(`/tenant/websites/${wid}/campaigns/${cid}`, { method: "DELETE" }),
  campaignAnalytics: (wid: string, cid: string) =>
    api<CampaignAnalytics>(`/tenant/websites/${wid}/campaigns/${cid}/analytics`),
  clearCampaignCache: (wid: string, cid: string) =>
    api<{ cleared: number }>(`/tenant/websites/${wid}/campaigns/${cid}/cache/clear`, { method: "POST" }),
  modelProvider: () => api<ModelProvider>("/tenant/model-provider"),
  saveModelProvider: (body: ModelProviderIn) =>
    api<ModelProvider>("/tenant/model-provider", { method: "PUT", body }),
  deleteModelProvider: () => api<void>("/tenant/model-provider", { method: "DELETE" }),
  testModelProvider: () =>
    api<{ ok: boolean; results: { role: string; model: string; ok: boolean; answered_by?: string; error?: string }[] }>(
      "/tenant/model-provider/test", { method: "POST" }),
  siteModel: (wid: string, byo_model: boolean) =>
    api<{ byo_model: boolean }>(`/tenant/websites/${wid}/model`, { method: "PUT", body: { byo_model } }),
  security: () => api<AccountSecurity>("/tenant/security"),
  saveSecurity: (require_mfa: boolean) =>
    api<{ require_mfa: boolean }>("/tenant/security", { method: "PUT", body: { require_mfa } }),
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
  templates: () => api<{ templates: TemplateSummary[] }>("/tenant/templates"),
  previewTemplate: (wid: string, template: string) =>
    api<TemplatePlan>(`/tenant/websites/${wid}/template/preview?template=${encodeURIComponent(template)}`),
  applyTemplate: (wid: string, template: string) =>
    api<TemplatePlan>(`/tenant/websites/${wid}/template`, { method: "POST", body: { template } }),
  createWebsite: (body: Partial<Website> & { template?: string | null }) =>
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

  // Generative experience (P0-7, P0-9): design system and component manifest.
  getDesignSystem: (id: string) => api<DesignSystemView>(`/tenant/websites/${id}/design-system`),
  saveDesignSystem: (id: string, body: DesignSystemInput) =>
    api<DesignSystemView>(`/tenant/websites/${id}/design-system`, { method: "PUT", body }),
  resetDesignSystem: (id: string) =>
    api<DesignSystemView>(`/tenant/websites/${id}/design-system`, { method: "DELETE" }),
  getManifest: (id: string) => api<ManifestView>(`/tenant/websites/${id}/manifest`),
  getManifestVersion: (id: string, v: number) =>
    api<ManifestVersion>(`/tenant/websites/${id}/manifest/versions/${v}`),
  createManifestVersion: (id: string, data: unknown, notes = "") =>
    api<ManifestVersion>(`/tenant/websites/${id}/manifest/versions`, { method: "POST", body: { data, notes } }),
  updateManifestDraft: (id: string, v: number, data: unknown, notes = "") =>
    api<ManifestVersion>(`/tenant/websites/${id}/manifest/versions/${v}`, { method: "PUT", body: { data, notes } }),
  deleteManifestDraft: (id: string, v: number) =>
    api<void>(`/tenant/websites/${id}/manifest/versions/${v}`, { method: "DELETE" }),
  approveManifestVersion: (id: string, v: number) =>
    api<ManifestVersion>(`/tenant/websites/${id}/manifest/versions/${v}/approve`, { method: "POST" }),
  draftManifestFromStorybook: (id: string, body: { url?: string; index?: unknown; docgen?: unknown }) =>
    api<ManifestVersion>(`/tenant/websites/${id}/manifest/drafts/storybook`, { method: "POST", body }),
  draftManifestFromSite: (id: string, body: { url?: string; max_pages?: number }) =>
    api<ManifestVersion>(`/tenant/websites/${id}/manifest/drafts/site`, { method: "POST", body }),
  // Adaptive regions (Phase 1): slots, intent families, plans.
  getRegionSettings: (id: string) => api<RegionSettings>(`/tenant/websites/${id}/regions/settings`),
  setRegionSettings: (id: string, regions_enabled: boolean, bandit?: Partial<Omit<RegionSettings, "regions_enabled">>) =>
    api<RegionSettings>(`/tenant/websites/${id}/regions/settings`, { method: "PUT", body: { regions_enabled, ...bandit } }),
  listRegions: (id: string) => api<{ regions: RegionSlot[]; components: { id: string; renderer: string; purpose: string }[] }>(
    `/tenant/websites/${id}/regions`),
  saveRegion: (id: string, name: string, body: Omit<RegionSlot, "id" | "name">) =>
    api<RegionSlot>(`/tenant/websites/${id}/regions/${encodeURIComponent(name)}`, { method: "PUT", body }),
  deleteRegion: (id: string, name: string) =>
    api<void>(`/tenant/websites/${id}/regions/${encodeURIComponent(name)}`, { method: "DELETE" }),
  listIntentFamilies: (id: string) => api<{ families: IntentFamily[] }>(`/tenant/websites/${id}/intent-families`),
  suggestIntentFamilies: (id: string) =>
    api<{ suggestions: Omit<IntentFamily, "id" | "enabled" | "updated_at">[] }>(`/tenant/websites/${id}/intent-families/suggest`),
  saveIntentFamily: (id: string, slug: string, body: Omit<IntentFamily, "id" | "slug" | "updated_at">) =>
    api<IntentFamily>(`/tenant/websites/${id}/intent-families/${encodeURIComponent(slug)}`, { method: "PUT", body }),
  deleteIntentFamily: (id: string, slug: string) =>
    api<void>(`/tenant/websites/${id}/intent-families/${encodeURIComponent(slug)}`, { method: "DELETE" }),
  resolveIntent: (id: string, page: string, signals: Record<string, string>) =>
    api<{ intent: ResolvedIntent; signal_text: string }>(`/tenant/websites/${id}/intent/resolve`,
      { method: "POST", body: { page, signals } }),
  listPlans: (id: string, family?: string) =>
    api<{ plans: PlanRow[] }>(`/tenant/websites/${id}/plans${family ? `?family=${encodeURIComponent(family)}` : ""}`),
  getPlan: (id: string, pid: string) => api<PlanView>(`/tenant/websites/${id}/plans/${pid}`),
  generatePlan: (id: string, body: { page: string; family?: string; persona?: string; lang?: string }) =>
    api<PlanView>(`/tenant/websites/${id}/plans/generate`, { method: "POST", body }),
  setPlanStatus: (id: string, pid: string, status: PlanStatus) =>
    api<PlanRow>(`/tenant/websites/${id}/plans/${pid}`, { method: "PUT", body: { status } }),
  deletePlan: (id: string, pid: string) => api<void>(`/tenant/websites/${id}/plans/${pid}`, { method: "DELETE" }),
  // Composed pages (Phase 2): routes, entities, connectors.
  listRoutes: (id: string) => api<{ routes: SiteRoute[]; hosted_base: string }>(`/tenant/websites/${id}/routes`),
  createRoute: (id: string, body: RouteInput) => api<SiteRoute>(`/tenant/websites/${id}/routes`, { method: "POST", body }),
  updateRoute: (id: string, rid: string, body: RouteInput) =>
    api<SiteRoute>(`/tenant/websites/${id}/routes/${rid}`, { method: "PUT", body }),
  deleteRoute: (id: string, rid: string) => api<void>(`/tenant/websites/${id}/routes/${rid}`, { method: "DELETE" }),
  setCanonical: (id: string, rid: string, plan: string | null) =>
    api<SiteRoute>(`/tenant/websites/${id}/routes/${rid}/canonical`, { method: "PUT", body: { plan } }),
  generateRoutePage: (id: string, rid: string, body: { family?: string; path?: string }) =>
    api<PlanRow & { preview_html: string; plan_id: string; intent: ResolvedIntent }>(
      `/tenant/websites/${id}/routes/${rid}/generate`, { method: "POST", body }),
  // Free-form pages (Phase 4): settings, fragments, review feed.
  getFreeform: (id: string) => api<FreeformSettings>(`/tenant/websites/${id}/freeform`),
  setFreeform: (id: string, body: Partial<FreeformSettings>) =>
    api<FreeformSettings>(`/tenant/websites/${id}/freeform`, { method: "PUT", body }),
  listFragments: (id: string, status?: string) =>
    api<{ fragments: Fragment[] }>(`/tenant/websites/${id}/fragments${status ? `?status_filter=${status}` : ""}`),
  setFragmentStatus: (id: string, fid: string, status: Fragment["status"]) =>
    api<{ id: string; status: string }>(`/tenant/websites/${id}/fragments/${fid}`, { method: "PUT", body: { status } }),
  listReviews: (id: string, status?: string) =>
    api<{ reviews: ReviewSample[] }>(`/tenant/websites/${id}/reviews${status ? `?status_filter=${status}` : ""}`),
  reviewSample: (id: string, rid: string, verdict: "ok" | "flagged") =>
    api<{ id: string; status: string }>(`/tenant/websites/${id}/reviews/${rid}`, { method: "PUT", body: { verdict } }),
  entityTypes: (id: string) => api<{ types: { type: string; count: number }[] }>(`/tenant/websites/${id}/entities`),
  listEntities: (id: string, type: string) =>
    api<{ records: EntityRecord[] }>(`/tenant/websites/${id}/entities/${encodeURIComponent(type)}`),
  saveEntity: (id: string, type: string, key: string, data: Record<string, unknown>) =>
    api<EntityRecord>(`/tenant/websites/${id}/entities/${encodeURIComponent(type)}/${encodeURIComponent(key)}`,
      { method: "PUT", body: { data } }),
  deleteEntity: (id: string, type: string, key: string) =>
    api<void>(`/tenant/websites/${id}/entities/${encodeURIComponent(type)}/${encodeURIComponent(key)}`, { method: "DELETE" }),
  importEntities: (id: string, body: { type: string; format: "json" | "csv"; key_field: string; content: string }) =>
    api<{ imported: number; problems: string[] }>(`/tenant/websites/${id}/entities/import`, { method: "POST", body }),
  listConnectors: (id: string) => api<{ connectors: Connector[] }>(`/tenant/websites/${id}/connectors`),
  createConnector: (id: string, body: ConnectorInput) =>
    api<Connector>(`/tenant/websites/${id}/connectors`, { method: "POST", body }),
  deleteConnector: (id: string, cid: string) => api<void>(`/tenant/websites/${id}/connectors/${cid}`, { method: "DELETE" }),
  syncConnector: (id: string, cid: string) =>
    api<{ status: string; records: number }>(`/tenant/websites/${id}/connectors/${cid}/sync`, { method: "POST" }),
};

// ---- composed pages (Phase 2) ----
export type RouteMode = "composed" | "freeform";
/** A region every free-form page on a route keeps, unchanged, at the top or bottom (Phase 4). */
export type PinnedRegion = { id: string; component: string; props?: Record<string, unknown>; position?: "top" | "bottom" };
export type RouteInput = { pattern: string; title: string; purpose: string; enabled: boolean; priority: number;
  mode?: RouteMode; pinned_regions?: PinnedRegion[] };
export type SiteRoute = RouteInput & { id: string; canonical_plan: string | null; plans: PlanRow[] };
export type EntityRecord = { id: string; type: string; key: string; data: Record<string, unknown>; source: string;
  updated_at: string | null };
export type ConnectorInput = { kind: "json_feed" | "wordpress"; name: string; url: string; entity_type: string;
  items_path: string; key_field: string; fields: Record<string, string> };
// ---- free-form pages (Phase 4) ----
export type FreeformSettings = { freeform_enabled: boolean; g3_daily_budget: number; g3_visitor_budget: number;
  review_sample_pct: number; g3_blocked_patterns: string[] };
export type Fragment = { id: string; purpose: string; component: string; region: Record<string, unknown>;
  conditions: { family?: string; lang?: string; taste?: string }; status: "auto" | "pinned" | "blocked";
  source: string; hit_count: number; rewards: number; created_at: string; last_hit_at: string | null };
export type ReviewSample = { id: string; route: string; plan_row: string | null; plan: Record<string, unknown>;
  flags: string[]; status: "new" | "ok" | "flagged"; created_at: string; reviewed_by: string | null;
  preview_html: string };
export type Connector = { id: string; kind: "json_feed" | "wordpress"; name: string; url: string; entity_type: string;
  config: Record<string, unknown>; last_sync_at: string | null; last_status: string };

// ---- adaptive regions (Phase 1) ----
export type RegionSlot = { id: string; name: string; label: string; purpose: string; components: string[];
  pages: string[]; enabled: boolean };
export type IntentRules = Partial<Record<"paths" | "utm_source" | "utm_medium" | "utm_campaign" |
  "referrer_hosts" | "query_terms", string[]>>;
export type IntentFamily = { id: string; slug: string; label: string; description: string; stage: string;
  rules: IntentRules; priority: number; enabled: boolean; updated_at: string | null };
export type ResolvedIntent = { family: string; label: string; stage: string; confidence: number;
  source: "rule" | "embedding" | "model" | "default" | "console"; matched: string[] };
export type PlanStatus = "auto" | "pinned" | "blocked";
export type PlanRow = { id: string; site_key: string; cache_key: string; family: string; persona: string; lang: string;
  page: string; regions: string[]; content_version: string; manifest_version: number | null;
  composer: "model" | "repaired" | "fallback" | "rules";
  status: PlanStatus; hit_count: number; build_ms: number; created_at: string; last_hit_at: string | null;
  taste?: string; arm?: number; base_key?: string; rewards?: number; reward_rate?: number | null };
/** Generated regions switch and region-level bandit settings (Phase 3). */
export type RegionSettings = { regions_enabled: boolean; bandit_enabled: boolean; max_arms: number; explore_pct: number };
export type PlanView = PlanRow & { plan: Record<string, unknown>; rendered: Record<string, unknown>;
  preview_html: string; intent?: ResolvedIntent; dropped?: string[]; problems?: string[] };

// ---- generative experience (P0-7) ----
export type Tunable = { allowed: string[]; default?: string | null };
export type DesignSystemInput = {
  name?: string; logo_url?: string; colors?: Record<string, string>;
  typography?: { font_family?: string; heading_family?: string; base_size?: string; scale?: number };
  radius?: string; brand_voice?: string; tunables?: Record<string, Tunable>;
  /** Palettes for the scheme tunable (Phase 3). */
  schemes?: Partial<Record<"light" | "dark", Record<string, string>>>;
};
export type DesignSystemDoc = Required<Omit<DesignSystemInput, "tunables" | "schemes">> & {
  tokens: Record<string, string>; tunables?: Record<string, Tunable>; schemes?: DesignSystemInput["schemes"];
};
export type DesignSystemView = {
  current: { data: DesignSystemInput; updated_at: string; updated_by: string | null } | null;
  effective: DesignSystemDoc;
  source: "console" | "file" | "extracted" | "default";
};
export type PropSpecDoc = { type: string; source: string; required?: boolean; max_items?: number;
  max_length?: number; enum?: string[] };
export type ManifestEntryDoc = { id: string; renderer: string; purpose: string; use_when: string[];
  avoid_when: string[]; actions: string[]; version: number; ssr: boolean; props: Record<string, PropSpecDoc> };
export type ManifestBundle = { url: string; integrity: string };
export type ManifestStatus = "draft" | "approved" | "archived";
export type ManifestVersionSummary = { id: string; site_key: string; version: number; status: ManifestStatus;
  source: "manual" | "storybook" | "site" | "file"; notes: string; created_at: string; created_by: string | null;
  approved_at: string | null; approved_by: string | null; components?: number };
export type ManifestVersion = ManifestVersionSummary & {
  data: Record<string, unknown>;
  check: { problems: string[]; components: ManifestEntryDoc[]; component_count: number; bundle: ManifestBundle | null };
};
export type ManifestView = {
  source: "default" | "file" | "console";
  active_version: number | null;
  active: ManifestVersion | null;
  effective: { bundle: ManifestBundle | null; components: ManifestEntryDoc[] };
  versions: ManifestVersionSummary[];
};
