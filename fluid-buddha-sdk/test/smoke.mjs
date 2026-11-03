// jsdom smoke test for the built SDK. Verifies the Shadow-DOM element builds,
// the Session routes envelopes, and the generative canvas renders components —
// all without a browser, mic, or network.
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' });
const { window } = dom;

// Wire the globals the bundle expects.
globalThis.window = window;
globalThis.document = window.document;
globalThis.customElements = window.customElements;
globalThis.HTMLElement = window.HTMLElement;
// `navigator` is a getter-only global on Node >= 20, so a plain assignment
// throws. Define it instead so the test runs on current Node unmodified.
Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
globalThis.CustomEvent = window.CustomEvent;
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
// Deterministic WebSocket stub (never actually connects).
globalThis.WebSocket = class {
  constructor(url) { this.readyState = 0; globalThis.__lastWsUrl = url; }
  close() {} send() {}
};

const mod = await import('../dist/fluid-buddha.mjs');
const { init, Session, Canvas, HostBridge } = mod;

let failures = 0;
const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`); if (!cond) failures++; };
const tick = () => new Promise((r) => setTimeout(r, 5));

// ---- 1. Element builds in a Shadow DOM ----
const el = init({ backend: 'ws://localhost:8080', site: 'hirebuddha' });
ok(!!el.shadowRoot, 'element attaches a shadow root');
ok(!!el.shadowRoot.querySelector('.trigger'), 'renders the floating trigger');
ok(!!el.shadowRoot.querySelector('.trigger canvas.trigger-aura'), 'launcher hosts a living Aura canvas');
ok(!!el.shadowRoot.querySelector('.avatar canvas'), 'header avatar is a living Aura canvas');
ok(!!el.shadowRoot.querySelector('.fb-grain'), 'film-grain film is present');
el.openPanel();
ok(!el.shadowRoot.querySelector('.panel').classList.contains('hidden'), 'openPanel reveals the panel');
ok(el.shadowRoot.querySelector('.panel').getAttribute('data-state') === 'dormant', 'panel starts in the dormant state-of-light');
ok(!!el.shadowRoot.querySelector('.bubble.pragya'), 'shows the greeting message');

// ---- 2. Session routes server envelopes ----
const calls = { persona: null, navigate: null, scroll: null };
const bridge = {
  setPersona: (p) => (calls.persona = p),
  navigate: (p) => (calls.navigate = p),
  scrollTo: (s) => (calls.scroll = s),
};
const events = { component: null, agent: null, transcript: null, page: null, patch: null };
const session = new Session(
  { backend: 'ws://x', api: 'http://x', site: 'hirebuddha', intelligence: 'extreme', design: 'level1', position: 'bottom-right', accent: '#000', greeting: '', autoInject: false, hooks: {} },
  bridge,
  {
    onStatus() {},
    onUserTranscript: (t) => (events.transcript = t),
    onAgentMessage: (t, g) => (events.agent = { t, g }),
    onComponent: (c) => (events.component = c),
    onPatch: (id, p) => (events.patch = { id, p }),
    onSystem() {},
    onPage: (p) => (events.page = p),
  },
);
session.feed({ channel: 'EVENTS', type: 'ready', payload: { config: { sample_rate: 24000, filler_delay_ms: 1500 } } });
session.feed({ channel: 'STATE', type: 'transcript', payload: { text: 'how does pricing work' } });
ok(events.transcript === 'how does pricing work', 'STATE/transcript -> onUserTranscript');
session.feed({ channel: 'EVENTS', type: 'set_persona', payload: { persona: 'startups' } });
ok(calls.persona === 'startups', 'EVENTS/set_persona -> bridge.setPersona');
session.feed({ channel: 'EVENTS', type: 'navigate', payload: { path: '/pricing' } });
ok(calls.navigate === '/pricing', 'EVENTS/navigate -> bridge.navigate');
session.feed({ channel: 'DATA', type: 'render', payload: { sync_id: 'ui_1', component_type: 'flowchart', initial_state: { nodes: [{ id: 'a', label: 'A' }] } } });
ok(events.component && events.component.component_type === 'flowchart', 'DATA/render -> onComponent');
session.feed({ channel: 'AUDIO', type: 'start', sync_id: 'ui_1', payload: { text: 'Here is the flow', grounding: { found: true, confidence: 0.9, sources: [] } } });
ok(events.agent && events.agent.t === 'Here is the flow' && events.agent.g.found, 'AUDIO/start(answer) -> onAgentMessage w/ grounding');
session.feed({ channel: 'AUDIO', type: 'start', sync_id: 'ack_1', payload: { text: 'one moment' } });
ok(events.agent.t === 'Here is the flow', 'AUDIO/start(ack) is NOT surfaced as a message');
session.feed({ channel: 'DATA', type: 'render_page', sync_id: 'page_1', payload: { sync_id: 'page_1', title: 'Welcome', sections: [{ type: 'hero', props: { title: 'Hi' } }] } });
ok(events.page && events.page.title === 'Welcome' && events.page.sections.length === 1, 'DATA/render_page -> onPage');
session.feed({ channel: 'DATA', type: 'patch', sync_id: 'ui_1', payload: { target_sync_id: 'ui_1', patch: { seats: 50 }, animation: 'count_up' } });
ok(events.patch && events.patch.id === 'ui_1' && events.patch.p.seats === 50, 'DATA/patch -> onPatch(target, patch)');

// ---- 3. Canvas renders components ----
const container = document.createElement('div');
let rendered = null;
const canvas = new Canvas(container, (id) => (rendered = id));
canvas.add({ sync_id: 'ui_9', component_type: 'flowchart', initial_state: { nodes: [{ label: 'Your system' }, { label: 'API' }], edges: [{ from: 'a', to: 'b' }] }, explanation_text: 'flow' });
ok(!!container.querySelector('.card .flow-node'), 'Canvas renders a flowchart card');
canvas.add({ sync_id: 'ui_10', component_type: 'roi_calculator', initial_state: { seats: 10, monthly_cost: 10000, hours_saved: 320 } });
ok(!!container.querySelector('.roi'), 'Canvas renders an ROI calculator');
await tick();
ok(rendered === 'ui_10', 'Canvas signals onRendered after paint');
canvas.applyPatch('ui_10', { monthly_cost: 20000 });
ok(container.querySelectorAll('.roi').length === 1, 'applyPatch rebuilds the card in place');

// ---- 3b. New Advance component types render ----
canvas.add({ sync_id: 'ui_wf', component_type: 'workflow', initial_state: { steps: [{ id: 's', label: 'Start', type: 'start' }, { id: 'p', label: 'Review', type: 'process' }] } });
ok(!!container.querySelector('.wf .wf-node'), 'Canvas renders a workflow diagram');
canvas.add({ sync_id: 'ui_cd', component_type: 'component_diagram', initial_state: { components: [{ id: 'fe', label: 'Frontend' }, { id: 'be', label: 'Backend' }], connections: [{ from: 'fe', to: 'be' }] } });
ok(!!container.querySelector('.cdiag svg .cdiag-box'), 'Canvas renders a component diagram');
canvas.add({ sync_id: 'ui_g', component_type: 'graph', initial_state: { nodes: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }], edges: [{ from: 'a', to: 'b' }] } });
ok(!!container.querySelector('.graph svg .graph-node'), 'Canvas renders a node-link graph');
canvas.add({ sync_id: 'ui_ch', component_type: 'chart', initial_state: { chart_type: 'bar', data: [{ label: 'Q1', value: 10 }, { label: 'Q2', value: 20 }] } });
ok(!!container.querySelector('.chart svg .chart-bar'), 'Canvas renders a bar chart');

// ---- 3c. Complex + interactive components (Features 3 & 4) ----
canvas.add({ sync_id: 'ui_mm', component_type: 'mind_map', initial_state: { topic: 'Hiring', branches: [{ label: 'Source', children: [{ label: 'Referrals' }] }, { label: 'Screen' }] } });
ok(!!container.querySelector('.mindmap svg .mm-node'), 'Canvas renders a mind map');
canvas.add({ sync_id: 'ui_tl', component_type: 'timeline', initial_state: { events: [{ date: 'Wk 1', label: 'Setup', detail: 'Connect tools' }, { date: 'Wk 2', label: 'Launch' }] } });
ok(!!container.querySelector('.timeline .tl-stop'), 'Canvas renders a timeline');
canvas.add({ sync_id: 'ui_sk', component_type: 'sankey', initial_state: { links: [{ source: 'Leads', target: 'Demos', value: 40 }, { source: 'Demos', target: 'Won', value: 12 }] } });
ok(!!container.querySelector('.sankey .sk-link'), 'Canvas renders a sankey');
canvas.add({ sync_id: 'ui_sim', component_type: 'scenario_simulator', initial_state: { sliders: [{ key: 'seats', label: 'Seats', min: 1, max: 100, value: 10 }], series: [{ label: 'Cost', expr: 'seats * 50', format: 'currency' }] } });
ok(!!container.querySelector('.sim .sim-bar-fill'), 'Canvas renders a scenario simulator');
canvas.add({ sync_id: 'ui_tb', component_type: 'tabs', initial_state: { tabs: [{ label: 'A', body: 'First' }, { label: 'B', body: 'Second' }] } });
const tabBtns = container.querySelectorAll('.tabs .tabs-tab');
ok(tabBtns.length === 2 && !!container.querySelector('.tabs-panel'), 'Canvas renders a tabs explorer');
tabBtns[1].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
ok(container.querySelector('.tabs-panel').textContent === 'Second', 'tabs switch panel on click');

// Interactive components report their state to the host on change.
const container2 = document.createElement('div');
let reported = null;
const canvas2 = new Canvas(container2, () => {}, (id, patch) => (reported = { id, patch }));
canvas2.add({ sync_id: 'ui_cfg', component_type: 'configurator', initial_state: { controls: [{ key: 'hours', label: 'Hours', type: 'slider', min: 0, max: 100, value: 10 }], outputs: [{ label: 'Value', expr: 'hours * 45', format: 'currency' }] } });
ok(!!container2.querySelector('.cfg-row input[type=range]') && !!container2.querySelector('.cfg-out-val'), 'configurator renders sliders + outputs');
const rng = container2.querySelector('.cfg-row input[type=range]');
rng.value = '20';
rng.dispatchEvent(new window.Event('input'));
ok(container2.querySelector('.cfg-out-val').textContent.includes('900'), 'configurator recomputes output live (20 * 45 = $900)');
rng.dispatchEvent(new window.Event('change'));
ok(reported && reported.id === 'ui_cfg' && reported.patch.values.hours === 20, 'interactive component reports state on commit');

// ---- 4. Intelligence / design level config ----
const adv = init({ backend: 'ws://localhost:8080', site: 'hirebuddha' });
adv.openPanel();
const advBtns = [...adv.shadowRoot.querySelectorAll('.in-btn')];
ok(!advBtns.some((b) => b.classList.contains('hidden')), 'advance (default) keeps the mic button visible');
const basic = init({ backend: 'ws://localhost:8080', site: 'hirebuddha', intelligence: 'basic' });
basic.openPanel();
const basicBtns = [...basic.shadowRoot.querySelectorAll('.in-btn')];
ok(basicBtns.some((b) => b.classList.contains('hidden')), 'basic tier hides the mic button (text-only)');

// ---- 5. Design Level 2 mounts the panel-less immersive shell ----
// (WebGL is unavailable in jsdom; the shell degrades gracefully without particles.)
const l2 = init({ backend: 'ws://localhost:8080', site: 'hirebuddha', design: 'level2' });
ok(!!l2.shadowRoot.querySelector('.l2'), 'level2 mounts the immersive overlay');
ok(!!l2.shadowRoot.querySelector('.l2-play'), 'level2 shows the play button');
ok(!!l2.shadowRoot.querySelector('.l2-input textarea'), 'level2 shows the bottom text box');
ok(!!l2.shadowRoot.querySelector('.l2-stack'), 'level2 has a message stack');
ok(!!l2.shadowRoot.querySelector('.l2-halo'), 'level2 has a reactive presence halo');
ok(!l2.shadowRoot.querySelector('.panel'), 'level2 has no chat panel');

// ---- 5b. Design Level 3 mounts the ambient atmosphere (no widget) ----
const l3 = init({ backend: 'ws://localhost:8080', site: 'hirebuddha', design: 'level3' });
ok(!!l3.shadowRoot.querySelector('.l3'), 'level3 mounts the atmosphere overlay');
ok(!!l3.shadowRoot.querySelector('.l3-aura'), 'level3 has a breathing edge-aura');
ok(!!l3.shadowRoot.querySelector('.l3-veil') && !!l3.shadowRoot.querySelector('.l3-ring'), 'level3 has the spotlight veil + ring');
ok(!!l3.shadowRoot.querySelector('.l3-seed'), 'level3 shows the summon mote');
ok(!!l3.shadowRoot.querySelector('.l3-summon canvas.l3-orb'), 'level3 summon hosts an Aura orb');
ok(!!l3.shadowRoot.querySelector('.l3-caps'), 'level3 has a caption layer');
ok(!l3.shadowRoot.querySelector('.panel') && !l3.shadowRoot.querySelector('.l2'), 'level3 has no panel and no level2 overlay');
// The atmosphere stays asleep (edge-aura dark) until summoned.
ok(!l3.shadowRoot.querySelector('.l3').classList.contains('awake'), 'level3 atmosphere is dormant until summoned');
l3.shadowRoot.querySelector('.l3-seed').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
ok(l3.shadowRoot.querySelector('.l3').classList.contains('summoning'), 'tapping the mote opens the summon');
ok(l3.shadowRoot.querySelector('.l3').classList.contains('awake'), 'summoning awakens the atmosphere');

// ---- 6. Extreme intelligence mounts a full-page render surface ----
const ext = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', site: 'fluidbuddha', intelligence: 'extreme', design: 'level1' });
ok(!!ext.shadowRoot.querySelector('.fbpage'), 'extreme mounts a runtime page surface');
ok(ext.shadowRoot.querySelector('.fbpage').classList.contains('hidden'), 'page surface is hidden until a page renders');

// ---- 7. Persona cross-fade (Req 3.6.3) ----
// matchMedia is undefined in jsdom -> not reduced-motion -> the veil path runs.
const customHooks = { persona: null };
const hb = new HostBridge({ onSetPersona: (p) => (customHooks.persona = p) });
hb.setPersona('enterprise');
ok(!!document.querySelector('[data-fb-persona-veil]'), 'persona switch mounts a cross-fade veil');
await new Promise((r) => setTimeout(r, 250));
ok(customHooks.persona === 'enterprise', 'host onSetPersona hook fires at the cross-fade peak');
await new Promise((r) => setTimeout(r, 250));
ok(!document.querySelector('[data-fb-persona-veil]'), 'cross-fade veil is removed after the switch');
// Default (hookless) path sets the data attribute the host CSS keys off.
new HostBridge({}).setPersona('startups');
await new Promise((r) => setTimeout(r, 250));
ok(document.documentElement.getAttribute('data-fb-persona') === 'startups', 'default path sets data-fb-persona');

// ---- Widget key reaches the backend ----
const keyed = new Session(
  { backend: 'ws://x', api: 'http://x', site: 'hirebuddha', key: 'fbk_test123', intelligence: 'advance', design: 'level1', position: 'bottom-right', accent: '#000', greeting: '', autoInject: false, hooks: {} },
  bridge,
  { onStatus() {}, onUserTranscript() {}, onAgentMessage() {}, onComponent() {}, onPatch() {}, onSystem() {}, onPage() {} },
);
keyed.connect();
ok(new URL(globalThis.__lastWsUrl).searchParams.get('key') === 'fbk_test123', 'widget key is sent on the voice socket');

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
