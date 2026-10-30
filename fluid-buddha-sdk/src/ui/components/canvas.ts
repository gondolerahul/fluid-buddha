// Generative UI canvas (arch §4.1). Maps DATA component payloads to safe,
// pre-built renderers — the LLM never emits raw HTML. After a card paints it
// calls onRendered(sync_id) so the jitter buffer can release the synced audio.

import { ComponentPayload } from '../../protocol';
import { buildFlowchart } from './flowchart';
import { buildRoiCalculator } from './roiCalculator';
import { buildComparisonTable } from './comparisonTable';
import { buildWorkflowDiagram } from './workflowDiagram';
import { buildComponentDiagram } from './componentDiagram';
import { buildGraph } from './graph';
import { buildChart } from './chart';
import { buildMindMap } from './mindMap';
import { buildTimeline } from './timeline';
import { buildSankey } from './sankey';
import { buildConfigurator } from './configurator';
import { buildScenarioSimulator } from './scenarioSimulator';
import { buildTabs } from './tabs';
import { RenderContext } from './interactive';

const nextFrame: (cb: () => void) => void =
  typeof requestAnimationFrame === 'function'
    ? (cb) => requestAnimationFrame(cb)
    : (cb) => setTimeout(cb, 0);

function buildBody(
  payload: ComponentPayload,
  patch?: Record<string, unknown>,
  ctx?: RenderContext,
): HTMLElement {
  const state = patch ? { ...payload.initial_state, ...patch } : payload.initial_state;
  switch (payload.component_type) {
    case 'flowchart':
      return buildFlowchart(state);
    case 'workflow':
      return buildWorkflowDiagram(state);
    case 'component_diagram':
      return buildComponentDiagram(state);
    case 'graph':
      return buildGraph(state);
    case 'chart':
      return buildChart(state);
    case 'roi_calculator':
      return buildRoiCalculator(state);
    case 'table':
      return buildComparisonTable(state);
    case 'mind_map':
      return buildMindMap(state, ctx);
    case 'timeline':
      return buildTimeline(state);
    case 'sankey':
      return buildSankey(state);
    case 'configurator':
      return buildConfigurator(state, ctx);
    case 'scenario_simulator':
      return buildScenarioSimulator(state, ctx);
    case 'tabs':
      return buildTabs(state, ctx);
    default: {
      const d = document.createElement('div');
      d.className = 'empty';
      d.textContent = `Unknown component: ${payload.component_type}`;
      return d;
    }
  }
}

export class Canvas {
  private cards = new Map<string, { card: HTMLElement; payload: ComponentPayload }>();

  constructor(
    private readonly container: HTMLElement,
    private readonly onRendered: (syncId: string) => void,
    /** Optional: receive a component's interactive state when the user plays
     *  with it (forwarded to the agent). */
    private readonly onState?: (syncId: string, patch: Record<string, unknown>) => void,
  ) {}

  private buildCard(payload: ComponentPayload, patch?: Record<string, unknown>): HTMLElement {
    const card = document.createElement('div');
    card.className = 'card';
    if (payload.explanation_text) {
      const cap = document.createElement('div');
      cap.className = 'caption';
      cap.textContent = payload.explanation_text;
      card.appendChild(cap);
    }
    const ctx: RenderContext = {
      syncId: payload.sync_id,
      reportState: this.onState
        ? (p) => this.onState!(payload.sync_id, p)
        : undefined,
    };
    card.appendChild(buildBody(payload, patch, ctx));
    return card;
  }

  add(payload: ComponentPayload): void {
    if (this.cards.has(payload.sync_id)) return;
    const card = this.buildCard(payload);
    this.container.appendChild(card);
    this.cards.set(payload.sync_id, { card, payload });
    nextFrame(() => this.onRendered(payload.sync_id));
  }

  applyPatch(syncId: string, patch: Record<string, unknown>): void {
    const entry = this.cards.get(syncId);
    if (!entry) return;
    const replacement = this.buildCard(entry.payload, patch);
    entry.card.replaceWith(replacement);
    this.cards.set(syncId, { card: replacement, payload: entry.payload });
  }

  clear(): void {
    this.container.replaceChildren();
    this.cards.clear();
  }
}
