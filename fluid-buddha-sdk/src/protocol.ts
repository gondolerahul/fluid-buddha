// Multiplexed transport protocol — mirrors the backend app/transport/envelope.py.

export type Channel = 'AUDIO' | 'DATA' | 'EVENTS' | 'STATE';

export interface Envelope {
  channel: Channel;
  type: string;
  payload: Record<string, unknown>;
  sync_id?: string | null;
  timestamp?: number;
}

/** The strongly-typed component kinds the agent can render in the canvas. */
export type ComponentType =
  | 'flowchart'
  | 'workflow'
  | 'component_diagram'
  | 'graph'
  | 'chart'
  | 'roi_calculator'
  | 'table'
  // Complex + interactive diagrams / widgets (Features 3 & 4):
  | 'mind_map'
  | 'timeline'
  | 'sankey'
  | 'configurator'
  | 'scenario_simulator'
  | 'tabs';

// ---- per-component strongly-typed `initial_state` shapes --------------------
export interface FlowchartState {
  nodes: Array<{ id?: string; label?: string }>;
  edges?: Array<{ from?: string; to?: string }>;
}
export interface WorkflowState {
  steps: Array<{ id?: string; label?: string; type?: 'start' | 'process' | 'decision' | 'end' }>;
  transitions?: Array<{ from?: string; to?: string; label?: string }>;
}
export interface ComponentDiagramState {
  components: Array<{ id?: string; label?: string; group?: string }>;
  connections?: Array<{ from?: string; to?: string; label?: string }>;
}
export interface GraphState {
  nodes: Array<{ id?: string; label?: string }>;
  edges?: Array<{ from?: string; to?: string; label?: string }>;
  directed?: boolean;
}
export interface ChartState {
  chart_type?: 'bar' | 'line' | 'pie';
  title?: string;
  unit?: string;
  data: Array<{ label?: string; value?: number }>;
}
export interface RoiCalculatorState {
  seats?: number;
  monthly_cost?: number;
  hours_saved?: number;
}
export interface TableState {
  headers?: string[];
  rows: Array<Array<string | number>>;
}
export interface MindMapState {
  topic?: string;
  branches: Array<{ label?: string; children?: Array<{ label?: string }> }>;
}
export interface TimelineState {
  events: Array<{ date?: string; label?: string; detail?: string }>;
}
export interface SankeyState {
  nodes?: Array<{ id?: string; label?: string; column?: number }>;
  links: Array<{ source?: string; target?: string; value?: number }>;
}
export interface ConfiguratorState {
  controls: Array<{
    key?: string; label?: string; type?: 'slider' | 'toggle' | 'select';
    min?: number; max?: number; step?: number; value?: number; unit?: string;
    options?: Array<{ label?: string; value?: number }>;
  }>;
  outputs?: Array<{ label?: string; expr?: string; unit?: string; format?: 'currency' | 'percent' | 'number' }>;
}
export interface ScenarioSimulatorState {
  sliders: Array<{ key?: string; label?: string; min?: number; max?: number; step?: number; value?: number; unit?: string }>;
  series: Array<{ label?: string; expr?: string; format?: 'currency' | 'percent' | 'number'; unit?: string }>;
}
export interface TabsState {
  tabs: Array<{ label?: string; body?: string }>;
}

export interface ComponentPayload {
  sync_id: string;
  component_type: ComponentType;
  initial_state: Record<string, unknown>;
  explanation_text?: string;
}

/** A section of a runtime-generated page (Extreme intelligence). */
export interface PageSection {
  type: string;
  props?: Record<string, unknown>;
}

/** A full page composed by the agent at runtime (Extreme intelligence). */
export interface PageSpec {
  sync_id: string;
  title: string;
  sections: PageSection[];
}

export interface Grounding {
  confidence: number;
  found: boolean;
  /** One entry per source document; `label` is display-ready, `route` is the
   *  site page it came from (when known). */
  sources: Array<{ document?: string; section?: string; score?: number; label?: string; route?: string }>;
}

/** The site's privacy settings, sent on `ready` (WS8). `retention_days` 0 means
 *  transcripts are kept until deleted; null when unknown (socket unavailable). */
export interface Privacy {
  consent_required: boolean;
  policy_url?: string | null;
  retention_days: number | null;
  redacts_pii: boolean;
}

export const base64ToBytes = (b64: string): Uint8Array => {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

export const bytesToBase64 = (bytes: Uint8Array): string => {
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
};
