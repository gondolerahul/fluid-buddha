// Every component renderer, keyed by component_type (arch §4.1). The LLM never
// emits raw HTML: a DATA payload names a type and its state, and one of these
// pre-built renderers draws it.
//
// The widget loads this module on demand (load.ts / load.global.ts): most
// visitors never see a diagram, so the renderers stay out of the core script
// (M2-7 made room for the language table this way). The recap page bundle
// imports it directly.

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

export type BuildBody = (
  payload: ComponentPayload,
  patch?: Record<string, unknown>,
  ctx?: RenderContext,
) => HTMLElement;

export const buildBody: BuildBody = (payload, patch, ctx) => {
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
};
