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
Object.defineProperty(globalThis, 'localStorage', { value: window.localStorage, configurable: true });
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
// Deterministic WebSocket stub (never actually connects).
globalThis.WebSocket = class {
  constructor(url) { this.readyState = 0; globalThis.__lastWsUrl = url; }
  close() {} send() {}
};

const mod = await import('../dist/fluid-buddha.mjs');
const { init, Session, Canvas, HostBridge, preloadComponents } = mod;

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

// ---- 2b. The enquiry form posts a lead straight to /leads (no LLM) ----
const posted = [];
globalThis.fetch = async (url, init) => { posted.push({ url, body: JSON.parse(init.body) }); return { ok: true, json: async () => ({ ok: true }) }; };
session.feed({ channel: 'EVENTS', type: 'ready', payload: { session_id: 'ws-123', config: {} } });
const leadOk = await session.submitLead({ email: 'ana@acme.io', name: 'Ana' });
ok(leadOk && posted.length === 1 && posted[0].url === 'http://x/leads', 'submitLead posts to /leads');
ok(posted[0].body.session_id === 'ws-123' && posted[0].body.values.email === 'ana@acme.io' && !('message' in posted[0].body), 'lead carries the voice session id and raw form values, not a chat message');

// ---- 3. Canvas renders components ----
// The renderers load on demand (M2-7): before they arrive a card waits, and
// its synced speech is released only once it is drawn.
const container = document.createElement('div');
let rendered = null;
const canvas = new Canvas(container, (id) => (rendered = id));
canvas.add({ sync_id: 'ui_early', component_type: 'flowchart', initial_state: { nodes: [{ label: 'Early' }] } });
ok(!!container.querySelector('.card .card-wait') && rendered === null, 'a card waits for the renderers, speech held');
await preloadComponents();
await tick();
ok(!container.querySelector('.card-wait') && !!container.querySelector('.card .flow-node') && rendered === 'ui_early',
  'the waiting card is drawn once the renderers arrive, then speech is released');
container.replaceChildren();
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

// ---- 5c. Grounded answers show their sources in every design level (WS8) ----
const cited = { found: true, confidence: 0.82, sources: [
  { label: 'Pricing', route: '/pricing', section: 'Plans' }, { label: 'Security' }] };
for (const design of ['level1', 'level2', 'level3']) {
  let opened = null;
  const w = init({ backend: 'ws://localhost:8080', site: 'hirebuddha', design, hooks: { onNavigate: (p) => (opened = p) } });
  if (design === 'level1') w.openPanel();
  w.session.feed({ channel: 'AUDIO', type: 'start', sync_id: 'utt_c1', payload: { text: 'Plans start small.', grounding: cited } });
  const chips = [...w.shadowRoot.querySelectorAll('.sources .source')];
  ok(chips.map((c) => c.textContent).join(',') === 'Pricing,Security', `${design}: grounded answer lists its sources`);
  chips[0].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  ok(opened === '/pricing' && chips[1].tagName === 'SPAN', `${design}: a source with a route opens that page`);
  w.session.feed({ channel: 'AUDIO', type: 'start', sync_id: 'utt_c2', payload: { text: 'Not sure.', grounding: { found: false, confidence: 0.1, sources: [] } } });
  ok(w.shadowRoot.querySelectorAll('.sources').length === 1, `${design}: an ungrounded answer shows no sources`);
}

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

// ---- Microphone consent (WS8) ----
const { consentCopy, consentPrompt } = mod;
const priv = { consent_required: true, retention_days: 30, redacts_pii: true, policy_url: 'https://example.com/privacy' };
const copy = consentCopy(priv);
ok(copy.includes('not stored') && copy.includes('30 days') && copy.includes('masked'), 'consent copy states audio, masking and retention');
const host = document.createElement('div');
document.body.appendChild(host);
const sroot = host.attachShadow({ mode: 'open' });
const allowP = consentPrompt(sroot, priv);
const dlg = sroot.querySelector('.fb-consent [role=dialog]');
ok(!!dlg && dlg.getAttribute('aria-modal') === 'true', 'consent prompt renders a modal dialog');
ok(sroot.querySelector('.fb-consent a').href === 'https://example.com/privacy', 'consent prompt links the privacy policy');
sroot.querySelector('.fb-consent-allow').click();
ok((await allowP) === true && !sroot.querySelector('.fb-consent'), 'Allow resolves true and closes the prompt');
const denyP = consentPrompt(sroot, { ...priv, policy_url: 'javascript:alert(1)' });
ok(!sroot.querySelector('.fb-consent a'), 'a non-web policy link is not rendered');
sroot.querySelector('.fb-consent-card').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
ok((await denyP) === false, 'Escape declines');

const cfgC = { backend: 'ws://x', api: 'http://x', site: 'consent-site', intelligence: 'advance', design: 'level1', position: 'bottom-right', accent: '#000', greeting: '', autoInject: false, hooks: {} };
const asked = [];
const sys = [];
let answer = false;
const cs = new Session(cfgC, bridge, {
  onStatus() {}, onUserTranscript() {}, onAgentMessage() {}, onComponent() {}, onPatch() {},
  onSystem: (m) => sys.push(m), onPage() {},
  requestConsent: async (p) => { asked.push(p); return answer; },
});
cs.feed({ channel: 'EVENTS', type: 'ready', payload: { session_id: 'c1', config: {}, privacy: priv } });
await cs.startVoice();
ok(asked.length === 1 && !cs.active && sys.at(-1).startsWith('Voice is off'), 'declining consent keeps the mic off');
answer = true;
await cs.startVoice();
ok(asked.length === 2 && window.localStorage.getItem('fluidbuddha:consent:consent-site') === '1', 'allowing consent is remembered for the site');
await cs.startVoice();
ok(asked.length === 2, 'a remembered consent is not asked again');
const noAsk = new Session({ ...cfgC, site: 'open-site' }, bridge, {
  onStatus() {}, onUserTranscript() {}, onAgentMessage() {}, onComponent() {}, onPatch() {},
  onSystem() {}, onPage() {}, requestConsent: async () => { asked.push('x'); return true; },
});
noAsk.feed({ channel: 'EVENTS', type: 'ready', payload: { config: {}, privacy: { ...priv, consent_required: false } } });
await noAsk.startVoice();
ok(asked.length === 2, 'a site that does not require consent skips the prompt');

// ---- WS5: binary audio frames ----
const { packAudio, unpackAudio, SpeechGate } = mod;
const pcmIn = new Uint8Array([1, 0, 2, 0, 3, 0]);
const frameOut = unpackAudio(packAudio('utt_abc', pcmIn).buffer);
ok(frameOut && frameOut.syncId === 'utt_abc' && frameOut.pcm.join() === '1,0,2,0,3,0', 'binary audio frame round-trips id + pcm');
ok(unpackAudio(new Uint8Array([2, 0, 1]).buffer) === null, 'a non-audio binary frame is ignored');

const sockets = [];
const RealWS = globalThis.WebSocket;
globalThis.WebSocket = class {
  static OPEN = 1;
  constructor(url) { this.url = url; this.readyState = 1; this.sent = []; sockets.push(this); }
  send(d) { this.sent.push(d); } close() {}
};
let agentAudio = 0;
const bs = new Session(
  { backend: 'ws://x', api: 'http://x', site: 'bin-site', intelligence: 'advance', design: 'level1', position: 'bottom-right', accent: '#000', greeting: '', autoInject: false, hooks: {} },
  bridge,
  { onStatus() {}, onUserTranscript() {}, onAgentMessage() {}, onComponent() {}, onPatch() {}, onSystem() {}, onPage() {}, onAgentAudio: () => agentAudio++ },
);
bs.connect();
const sock = sockets.at(-1);
ok(new URL(sock.url).searchParams.get('audio') === 'binary' && sock.binaryType === 'arraybuffer', 'voice socket asks for binary audio frames');
bs.client.sendAudioChunk(pcmIn);
ok(typeof sock.sent.at(-1) === 'string' && JSON.parse(sock.sent.at(-1)).payload.data, 'mic audio is JSON until the server confirms binary');
sock.onmessage({ data: JSON.stringify({ channel: 'EVENTS', type: 'ready', payload: { config: { audio_frames: 'binary' } } }) });
bs.client.sendAudioChunk(pcmIn);
const sentFrame = sock.sent.at(-1);
ok(sentFrame instanceof Uint8Array && unpackAudio(sentFrame).pcm.length === 6, 'mic audio goes out as binary frames once confirmed');
sock.onmessage({ data: JSON.stringify({ channel: 'AUDIO', type: 'start', sync_id: 'utt_b1', payload: { text: 'Hi' } }) });
sock.onmessage({ data: packAudio('utt_b1', new Uint8Array(480)).buffer });
ok(agentAudio === 1, 'a binary TTS frame plays as the chunk of its segment');
globalThis.WebSocket = RealWS;

// ---- WS5: speech pre-roll ----
const gateEvents = [];
const gate = new SpeechGate({
  onChunk: (b) => gateEvents.push(['chunk', b.length]),
  onSpeechStart: () => gateEvents.push(['start']),
  onSpeechEnd: () => gateEvents.push(['end']),
});
const quiet = new Float32Array(960); // 20 ms @ 48 kHz
const loud = Float32Array.from({ length: 960 }, (_, i) => 0.2 * Math.sin(i / 4));
for (let i = 0; i < 10; i++) gate.process(quiet, 48000);
ok(gateEvents.length === 0, 'nothing is sent before speech');
for (let i = 0; i < 12; i++) gate.process(loud, 48000);
const startAt = gateEvents.findIndex((e) => e[0] === 'start');
const opening = gateEvents.slice(startAt + 1).reduce((n, e) => n + (e[0] === 'chunk' ? e[1] : 0), 0);
// Speech is declared after 180 ms of voice; the pre-roll must still deliver
// that onset plus lead-in. At 16 kHz PCM16 that is 640 bytes per 20 ms.
ok(startAt === 0 && opening >= 640 * 12, `utterance opens with its first words (${opening} bytes)`);
for (let i = 0; i < 50; i++) gate.process(quiet, 48000);
ok(gateEvents.some((e) => e[0] === 'end'), 'sustained silence ends the utterance');
let n44 = 0;
const g44 = new SpeechGate({ onChunk: (b) => (n44 += b.length / 2), onSpeechStart() {}, onSpeechEnd() {} });
const loud44 = Float32Array.from({ length: 1024 }, (_, i) => 0.2 * Math.sin(i / 4));
for (let i = 0; i < 100; i++) g44.process(loud44, 44100);
// The first ~180 ms (8 frames) open the utterance via the pre-roll, so all
// 100 frames should come out, resampled without drift.
const expect44 = (100 * 1024 * 16000) / 44100;
ok(Math.abs(n44 - expect44) <= 2, `44.1 kHz resampling doesn't drift (${n44} vs ${expect44.toFixed(1)} samples)`);

// ---- WS5 / D-15: navigation doesn't hard-reload single-page apps ----
class TestBridge extends HostBridge {
  constructor(...a) { super(...a); this.hard = []; }
  hardNavigate(href) { this.hard.push(href); }
}
const navigated = [];
window.addEventListener('fluidbuddha:navigated', (e) => navigated.push(e.detail.path));
const spaRender = () => document.body.appendChild(document.createElement('main'));
window.addEventListener('popstate', spaRender);
const nb = new TestBridge({});
nb.navigate('/pricing');
await new Promise((r) => setTimeout(r, 20));
ok(window.location.pathname === '/pricing' && nb.hard.length === 0 && navigated.at(-1) === '/pricing', 'a router that renders on popstate gets an in-app route change');
window.removeEventListener('popstate', spaRender);
nb.navigate('/pricing#plans');
ok(nb.hard.length === 0 && window.location.pathname === '/pricing', 'a same-page anchor only scrolls');
nb.navigate('/about');
await new Promise((r) => setTimeout(r, 700));
ok(nb.hard.at(-1) === 'http://localhost/about', 'a multi-page site (nothing re-renders) falls back to a page load');
nb.navigate('https://other.example/x');
ok(nb.hard.at(-1) === 'https://other.example/x', 'another origin is a normal page load');
const cancelNav = (e) => e.preventDefault();
window.addEventListener('fluidbuddha:navigate', cancelNav);
const before = window.location.pathname;
nb.navigate('/contact');
await new Promise((r) => setTimeout(r, 20));
ok(window.location.pathname === before && nb.hard.at(-1) === 'https://other.example/x', 'cancelling fluidbuddha:navigate leaves routing to the host');
window.removeEventListener('fluidbuddha:navigate', cancelNav);
const rb = new TestBridge({}, 'reload');
rb.navigate('/team');
ok(rb.hard.at(-1) === 'http://localhost/team', "navigation: 'reload' always loads the page");

// ---- WS5: Level 2 reopens after close ----
const l2b = init({ backend: 'ws://localhost:8080', site: 'hirebuddha', design: 'level2' });
const l2root = l2b.shadowRoot.querySelector('.l2');
const reopen = l2b.shadowRoot.querySelector('.l2-reopen');
ok(!!reopen && reopen.classList.contains('l2-hidden'), 'level2 reopen orb is hidden while open');
l2b.shadowRoot.querySelector('.l2-close').click();
ok(l2root.classList.contains('l2-hidden') && !reopen.classList.contains('l2-hidden'), 'closing level2 leaves a reopen orb');
reopen.click();
ok(!l2root.classList.contains('l2-hidden') && reopen.classList.contains('l2-hidden'), 'the orb reopens level2');

// ---- WS5: Three.js is only in the Level 2 bundle ----
const fs = await import('node:fs');
const zlib = await import('node:zlib');
const coreJs = fs.readFileSync(new URL('../dist/fluid-buddha.global.js', import.meta.url));
const particlesJs = fs.readFileSync(new URL('../dist/fluid-buddha-particles.global.js', import.meta.url));
const coreMjs = fs.readFileSync(new URL('../dist/fluid-buddha.mjs', import.meta.url), 'utf8');
ok(!coreJs.includes('WebGLRenderer') && particlesJs.includes('WebGLRenderer'), 'script-tag core ships without Three.js; the particles file has it');
ok(!coreMjs.includes('WebGLRenderer') && /import\(["']\.\/chunks\/ParticleField-/.test(coreMjs), 'ESM core loads the particle field as a split chunk');
const componentsJs = fs.readFileSync(new URL('../dist/fluid-buddha-components.global.js', import.meta.url), 'utf8');
ok(!coreJs.includes('Unknown component') && componentsJs.includes('Unknown component') && /import\(["']\.\/chunks\/bodies-/.test(coreMjs),
  'component renderers ship on their own (script-tag file, ESM chunk), not in the core');
const coreGz = zlib.gzipSync(coreJs).length;
ok(coreGz < 42 * 1024, `script-tag core is ${(coreGz / 1024).toFixed(1)} kB gzipped (budget 42 kB)`);

// ---- WS11: holdout A/B ----
const expCalls = [];
let enrolReply = null;
globalThis.fetch = async (url, init) => {
  const body = init && init.body ? JSON.parse(init.body) : {};
  expCalls.push({ url: String(url), body });
  if (String(url).endsWith('/experiment/enroll'))
    return { ok: true, json: async () => enrolReply };
  return { ok: true, json: async () => ({ counted: true }) };
};
const settle = () => new Promise((r) => setTimeout(r, 20));

enrolReply = { experiment_id: 'exp-1', arm: 'holdout', goal_path: '/thanks' };
const held = init({ backend: 'ws://localhost:8080', key: 'fbk_holdout_site', site: 'x' });
ok(!held.shadowRoot, 'a keyed widget waits for its arm before drawing');
await settle();
const enrolCall = expCalls.find((c) => c.url.endsWith('/experiment/enroll'));
ok(enrolCall && enrolCall.body.key === 'fbk_holdout_site' && /^[A-Za-z0-9_-]{8,64}$/.test(enrolCall.body.visitor),
  'enrols with the widget key and an anonymous visitor id');
ok(enrolCall.body.automated === false, 'reports whether the browser is automated (bots are kept out)');
ok(!held.shadowRoot && held.hasAttribute('data-holdout'), 'a holdout visitor gets no widget');
held.openPanel(); held.ask('hi'); held.close();
ok(!held.shadowRoot, 'host calls cannot bring the agent back for a holdout visitor');
ok(JSON.parse(window.localStorage.getItem('fluidbuddha:exp:fbk_holdout_site')).arm === 'holdout', 'the arm is cached for later page views');

window.history.pushState({}, '', '/thanks/');
await new Promise((r) => setTimeout(r, 1100));
const goalHit = expCalls.find((c) => c.url.endsWith('/experiment/convert') && c.body.name === 'goal_page');
ok(goalHit && goalHit.body.experiment_id === 'exp-1' && goalHit.body.visitor === enrolCall.body.visitor,
  'reaching the goal page counts a conversion in the holdout too');
mod.conversion('demo_booked', 120);
const custom = expCalls.find((c) => c.body.name === 'demo_booked');
ok(custom && custom.body.value === 120, 'FluidBuddha.conversion() reports a named goal');
held.remove();
window.history.pushState({}, '', '/');

// The same visitor on the next page view: decided at once from the cache.
expCalls.length = 0;
const again = init({ backend: 'ws://localhost:8080', key: 'fbk_holdout_site', site: 'x' });
ok(again.hasAttribute('data-holdout') && !again.shadowRoot, 'a cached arm is applied without waiting');
await settle();
ok(expCalls.some((c) => c.url.endsWith('/experiment/enroll')), 'the cached arm is refreshed in the background');
again.remove();

enrolReply = { experiment_id: 'exp-2', arm: 'agent', goal_path: null };
const agentEl = init({ backend: 'ws://localhost:8080', key: 'fbk_agent_site', site: 'x' });
await settle();
ok(!!agentEl.shadowRoot && !!agentEl.shadowRoot.querySelector('.trigger'), 'an agent-arm visitor gets the widget');
agentEl.remove();

enrolReply = { experiment_id: null, arm: null, goal_path: null };
const noExp = init({ backend: 'ws://localhost:8080', key: 'fbk_no_experiment', site: 'x' });
await settle();
ok(!!noExp.shadowRoot && window.localStorage.getItem('fluidbuddha:exp:fbk_no_experiment') === null,
  'without an experiment the widget shows as usual');
noExp.remove();

globalThis.fetch = async () => { throw new Error('offline'); };
const offline = init({ backend: 'ws://localhost:8080', key: 'fbk_offline_site', site: 'x' });
await settle();
ok(!!offline.shadowRoot, 'if enrolment fails the visitor just gets the agent');
offline.remove();

// ---- Live takeover: a person joins, talks, rings, hands back (M2-2) ----
{
  const sys = [], said = [], sent = [];
  const live = new Session(
    { backend: 'ws://x', api: 'http://x', site: 'hirebuddha', intelligence: 'advance', design: 'level1', position: 'bottom-right', accent: '#000', greeting: '', autoInject: false, hooks: {} },
    bridge,
    { onStatus() {}, onUserTranscript() {}, onAgentMessage: (t) => said.push(t), onComponent() {}, onPatch() {},
      onSystem: (m) => sys.push(m), onPage() {}, requestCall: async () => true },
  );
  live.client = { sendRaw: (channel, type, payload) => sent.push({ channel, type, payload }) };
  live.feed({ channel: 'EVENTS', type: 'operator_joined', payload: { name: 'Priya' } });
  ok(sys.some((m) => m.includes('Priya from the team joined')), 'the visitor is told who joined');
  live.feed({ channel: 'EVENTS', type: 'operator_message', payload: { name: 'Priya', text: 'Hi there' } });
  ok(said.includes('Priya: Hi there'), "the person's message shows with their name");
  live.feed({ channel: 'EVENTS', type: 'call_offer', payload: { name: 'Priya', sdp: 'v=0', ice_servers: [] } });
  await new Promise((r) => setTimeout(r, 0));
  ok(sent.some((x) => x.type === 'call_decline'), 'a call the browser cannot take is declined, not crashed');
  live.feed({ channel: 'EVENTS', type: 'operator_left', payload: { name: 'Priya' } });
  ok(sys.some((m) => m.includes('handed you back')), 'handing back is announced');

  const { callPrompt } = mod;
  const host = document.createElement('div');
  const root = host.attachShadow({ mode: 'open' });
  const answer = callPrompt(root, 'Priya');
  ok(root.querySelector('[role="alertdialog"]')?.textContent.includes('Talk with Priya?'), 'the call prompt names the person');
  root.querySelector('.fb-consent-deny').click();
  ok((await answer) === false && !root.querySelector('.fb-consent'), 'declining closes the prompt');
}

// ---- Proactive triggers (M2-3) ----
{
  const { pageMatches } = mod;
  ok(pageMatches('/pricing', ['/pricing']) && pageMatches('/pricing/teams', ['/pricing*'])
    && pageMatches('/anything', []) && !pageMatches('/blog', ['/pricing*']), 'trigger page globs match as expected');

  // A fresh visit: talking to the agent earlier in this file muted triggers for the session.
  window.sessionStorage.removeItem('fluidbuddha:trg:muted');
  const trg = [];
  const rules = [{ id: 'r1', kind: 'time_on_page', seconds: 0.05, pages: [], message: 'Need a hand with pricing?',
    action: 'nudge', max_per_day: 1, priority: 50 }];
  globalThis.fetch = async (url, init) => {
    const u = String(url);
    trg.push({ url: u, body: init && init.body ? JSON.parse(init.body) : null });
    if (u.includes('/experiment/enroll')) return { ok: true, json: async () => ({ experiment_id: null, arm: null, goal_path: null }) };
    if (u.includes('/widget/triggers?')) return { ok: true, json: async () => ({ rules }) };
    return { ok: true, json: async () => ({ counted: true }) };
  };
  const sent = (event) => trg.some((c) => c.url.endsWith('/widget/triggers/event') && c.body?.event === event && c.body.rule_id === 'r1');
  const w = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', key: 'fbk_trigger_site', site: 'x' });
  await settle();
  await new Promise((r) => setTimeout(r, 150));
  const nudge = w.shadowRoot.querySelector('.fb-nudge');
  ok(nudge && nudge.textContent.includes('Need a hand with pricing?'), 'a time-on-page trigger shows its nudge');
  ok(sent('shown'), 'showing it is reported');
  nudge.querySelector('.fb-nudge-msg').click();
  ok(!w.shadowRoot.querySelector('.fb-nudge') && !w.shadowRoot.querySelector('.panel').classList.contains('hidden'),
    'clicking the nudge opens the agent');
  ok(w.shadowRoot.textContent.includes('Need a hand with pricing?') && sent('clicked'), 'the agent opens with the message, and the click is reported');
  w.ask('Which plan fits a team of 20?');
  ok(sent('engaged'), 'asking something after the nudge counts as engaged');
  w.remove();

  window.sessionStorage.removeItem('fluidbuddha:trg:muted');
  const w2 = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', key: 'fbk_trigger_site', site: 'x' });
  await settle();
  await new Promise((r) => setTimeout(r, 150));
  ok(!w2.shadowRoot.querySelector('.fb-nudge'), 'a rule capped at once a day does not show again today');
  w2.remove();
}

// ---- Variant tests (M2-4) ----
{
  window.sessionStorage.removeItem('fluidbuddha:trg:muted');
  const calls = [];
  let reply = null;
  const rules = [{ id: 'r1', kind: 'time_on_page', seconds: 0.05, pages: [], message: 'Psst — questions?',
    action: 'nudge', max_per_day: 5, priority: 50 }];
  globalThis.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, body: init && init.body ? JSON.parse(init.body) : null });
    if (u.includes('/experiment/enroll')) return { ok: true, json: async () => reply };
    if (u.includes('/widget/triggers?')) return { ok: true, json: async () => ({ rules }) };
    if (u.endsWith('/chat')) return { ok: true, json: async () => ({ text: 'ok', session_id: 's1', actions: [], components: [] }) };
    return { ok: true, json: async () => ({ counted: true }) };
  };
  const opts = (key, extra = {}) => ({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', key, site: 'x', ...extra });

  reply = { experiment_id: 't-1', arm: 'b', goal_path: null,
    overrides: { greeting: 'Hello from B.', triggers: [] }, defaults: { greeting: 'Site hello.', design: 'level1' } };
  const v = init(opts('fbk_variant_site'));
  await settle();
  await new Promise((r) => setTimeout(r, 150));
  ok(v.shadowRoot.textContent.includes('Hello from B.') && !v.shadowRoot.textContent.includes('Site hello.'),
    "the variant's greeting replaces the site's");
  ok(!v.shadowRoot.querySelector('.fb-nudge'), "a trigger left out of the visitor's variant does not fire");
  ok(JSON.parse(window.localStorage.getItem('fluidbuddha:exp:fbk_variant_site')).overrides.greeting === 'Hello from B.',
    'the variant is cached with its arm');
  v.ask('What does it cost?');
  await settle();
  const chat = calls.find((c) => c.url.endsWith('/chat'));
  ok(chat && chat.body.exp && chat.body.exp.id === 't-1' && chat.body.exp.arm === 'b',
    'the variant goes with the conversation (the server applies persona/greeting)');
  v.remove();

  reply = { experiment_id: 't-2', arm: 'c', goal_path: null, overrides: { design: 'level2', tour: false }, defaults: {} };
  const d = init(opts('fbk_design_variant'));
  await settle();
  ok(d.getAttribute('data-design') === 'level2' && !!d.shadowRoot.querySelector('.l2'), 'a design variant switches the level');
  d.remove();

  reply = { experiment_id: null, arm: null, goal_path: null, overrides: {}, defaults: { greeting: 'Site hello.', design: 'level3' } };
  const s = init(opts('fbk_defaults_site'));
  await settle();
  ok(s.getAttribute('data-design') === 'level3', "without a test the site's design level applies");
  s.remove();
  const pinned = init(opts('fbk_defaults_site', { design: 'level1' }));
  await settle();
  ok(pinned.getAttribute('data-design') === 'level1' && pinned.shadowRoot.textContent.includes('Site hello.'),
    "an embed that sets its design keeps it, and shows the site's greeting");
  pinned.remove();
}

// ---- Recap pages (M2-6) ----
{
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, body: init && init.body ? JSON.parse(init.body) : null });
    if (u.includes('/experiment/enroll')) return { ok: true, json: async () => ({ experiment_id: null, arm: null, goal_path: null, overrides: {}, defaults: {} }) };
    if (u.endsWith('/chat')) return { ok: true, json: async () => ({ text: 'Plans start at 2,000.', session_id: 'sess-recap', actions: [], components: [] }) };
    if (u.endsWith('/recap')) return { ok: true, status: 200, json: async () => ({ url: 'https://api.example.com/r/tok123', emailed: true }) };
    return { ok: true, json: async () => ({}) };
  };
  const w = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', key: 'fbk_recap_site', site: 'x', design: 'level1' });
  await settle();
  w.ask('What does it cost?');
  await settle();
  w.ask('Please email me a recap at Ana@Example.com');
  await settle();
  const rc = calls.find((c) => c.url.endsWith('/recap'));
  ok(rc && rc.body.session_id === 'sess-recap' && rc.body.email === 'Ana@Example.com' && rc.body.key === 'fbk_recap_site',
    '"email me a recap" asks for a recap of this conversation, with the address');
  ok(!calls.some((c) => c.url.endsWith('/chat') && c.body.message.includes('recap')), 'the recap request is not sent to the agent');
  const link = [...w.shadowRoot.querySelectorAll('.bubble.pragya a')].find((a) => a.href === 'https://api.example.com/r/tok123');
  ok(link && link.target === '_blank' && link.rel.includes('noopener') && w.shadowRoot.textContent.includes('emailed it to Ana@Example.com'),
    'the recap link shows as a link, and says it was emailed');
  w.remove();

  // The recap page's renderer draws each component in its slot.
  const { readFile } = await import('node:fs/promises');
  const code = await readFile(new URL('../dist/fluid-buddha-recap.global.js', import.meta.url), 'utf8');
  document.body.innerHTML = '<div data-fb-slot="c0"><div class="comp-fallback">flow</div></div>'
    + '<div data-fb-slot="c1"></div><script type="application/json" id="fb-recap-data">'
    + JSON.stringify([{ slot: 'c0', component: { component_type: 'flowchart', initial_state: { nodes: [{ label: 'A' }, { label: 'B' }], edges: [] } } },
      { slot: 'c1', component: { component_type: 'roi_calculator', initial_state: { seats: 5, monthly_cost: 1000, hours_saved: 40 } } },
      { slot: 'nope', component: { component_type: 'chart' } }]) + '</script>';
  new Function(code)();
  const s0 = document.querySelector('[data-fb-slot="c0"]').shadowRoot;
  ok(s0 && s0.querySelector('.card .flow-node') && s0.querySelector('style').textContent.includes('.card'),
    'the recap page draws a flowchart with the widget styles');
  ok(document.querySelector('[data-fb-slot="c1"]').shadowRoot.querySelector('.roi'), 'and an ROI calculator');
  document.body.innerHTML = '';
}

// ---- English + Hindi (M2-7) ----
{
  const { STRINGS, pickLang, prepareLang } = mod;
  // The Hindi table ships on its own and is fetched only for Hindi visitors.
  const fs2 = await import('node:fs');
  const hiJs = fs2.readFileSync(new URL('../dist/fluid-buddha-hi.global.js', import.meta.url), 'utf8');
  ok(!coreJs.includes('प्रज्ञा') && !coreJs.includes('\\u092A\\u094D\\u0930\\u091C') && hiJs.includes('FluidBuddhaHindi'),
    'the Hindi words are not in the core script; they have their own file');
  ok(!STRINGS.hi, 'Hindi is not loaded until a Hindi widget needs it');

  // Language choice: embed attribute, the site's setting, the visitor's browser.
  ok(pickLang('hi', null) === 'hi' && pickLang(undefined, null) === 'en', 'without site settings only data-lang chooses');
  ok(pickLang('hi', { languages: ['en'] }) === 'en', 'a site without Hindi stays English even with data-lang="hi"');
  ok(pickLang(undefined, { languages: ['en', 'hi'], widget_language: 'hi' }) === 'hi', "the site's Hindi setting");
  ok(pickLang('en', { languages: ['en', 'hi'], widget_language: 'hi' }) === 'en', 'data-lang wins over the site setting');
  Object.defineProperty(window.navigator, 'languages', { value: ['hi-IN', 'en-US'], configurable: true });
  ok(pickLang(undefined, { languages: ['en', 'hi'], widget_language: 'auto' }) === 'hi', "auto follows a Hindi browser");
  Object.defineProperty(window.navigator, 'languages', { value: ['en-US'], configurable: true });
  ok(pickLang(undefined, { languages: ['en', 'hi'], widget_language: 'auto' }) === 'en', 'auto on an English browser is English');

  // String coverage: every English string has a Hindi one, same placeholders.
  await prepareLang('hi');
  const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
  const missing = Object.keys(STRINGS.en).filter((k) => !STRINGS.hi[k] || holes(STRINGS.hi[k]) !== holes(STRINGS.en[k]));
  ok(STRINGS.hi && missing.length === 0, `every widget string has a Hindi version (${Object.keys(STRINGS.en).length} strings)${missing.length ? ' — missing: ' + missing.join(', ') : ''}`);
  const latinOnly = Object.keys(STRINGS.hi).filter((k) => !/[ऀ-ॿ]/.test(STRINGS.hi[k]));
  ok(latinOnly.length === 0, `Hindi strings are in Devanagari${latinOnly.length ? ' — not: ' + latinOnly.join(', ') : ''}`);
  ok(Object.keys(STRINGS.hi).every((k) => k in STRINGS.en), 'no Hindi string without an English one');

  // A Hindi widget: labels, chips and greeting in Hindi; the hello says so.
  globalThis.fetch = async () => ({ ok: true, json: async () => ({}) });
  const hw = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', site: 'hirebuddha', lang: 'hi' });
  await settle();
  const root = hw.shadowRoot;
  ok(root && root.querySelector('textarea').placeholder === STRINGS.hi.placeholder, 'a Hindi widget shows its labels in Hindi');
  ok([...root.querySelectorAll('.chip')].map((c) => c.textContent).join('|') === [STRINGS.hi.chipPricing, STRINGS.hi.chipIntegrate, STRINGS.hi.chipTour].join('|'),
    'suggestion chips are in Hindi');
  ok(root.querySelector('.bubble.pragya').textContent.includes('नमस्ते'), 'the default greeting is in Hindi');
  hw.remove();

  // "Send me this" in Hindi asks for a recap.
  const rcalls = [];
  globalThis.fetch = async (url, init2) => {
    const u = String(url);
    rcalls.push(u);
    if (u.endsWith('/recap')) return { ok: true, status: 200, json: async () => ({ url: 'https://api.example.com/r/tokhi', emailed: false }) };
    return { ok: true, json: async () => ({ text: 'ok', session_id: 'sess-hi', lang: 'hi', actions: [], components: [] }) };
  };
  const rw = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', key: 'fbk_hi_site', site: 'x', lang: 'hi' });
  await settle();
  rw.ask('यह मुझे भेज दो');
  await settle();
  ok(rcalls.some((u) => u.endsWith('/recap')) && rw.shadowRoot.textContent.includes('यह रहा आपका रीकैप'),
    'a Hindi "send me this" makes a recap, answered in Hindi');
  rw.remove();
  await prepareLang('en');
}

// ---- Actions + custom components (M2-8) ----
{
  const posts = [];
  globalThis.fetch = async (url, init2) => {
    const u = String(url);
    const body = init2 && init2.body ? JSON.parse(init2.body) : null;
    posts.push({ u, body });
    if (u.includes('/experiment/enroll')) return { ok: true, json: async () => ({ defaults: {} }) };
    if (u.endsWith('/chat')) return { ok: true, json: async () => ({ text: 'Please confirm on screen.', session_id: 'sess-act', actions: [], components: [],
      proposals: [{ id: 'run-1', kind: 'payment_link', label: 'Pay for a plan', summary: [{ label: 'Plan', value: 'Growth plan' }, { label: 'Amount', value: '₹14,999' }] }] }) };
    if (u.endsWith('/actions/confirm')) return { ok: true, json: async () => ({ id: 'run-1', status: 'done', message: 'Payment link for Growth plan.', url: 'https://rzp.io/i/abc123' }) };
    if (u.endsWith('/actions/cancel')) return { ok: true, json: async () => ({ id: body.run_id, status: 'cancelled' }) };
    return { ok: true, json: async () => ({}) };
  };
  const aw = init({ backend: 'ws://localhost:8080', api: 'http://localhost:8080', key: 'fbk_act_site', site: 'x', design: 'level1' });
  await settle();
  aw.ask('I want to pay for the growth plan');
  await settle();
  const card = aw.shadowRoot.querySelector('.fb-action');
  ok(card && card.textContent.includes('Pay for a plan') && card.textContent.includes('₹14,999'),
    'a proposed action shows a confirmation card with its amount');
  ok(!posts.some((p) => p.u.includes('/actions/')), 'nothing is sent before the visitor confirms');
  card.querySelector('.fb-consent-allow').click();
  await settle();
  const conf = posts.find((p) => p.u.endsWith('/actions/confirm'));
  ok(conf && conf.body.run_id === 'run-1' && conf.body.session_id === 'sess-act' && conf.body.key === 'fbk_act_site',
    'Confirm posts the run for this conversation');
  const link = card.querySelector('a.fb-consent-allow');
  ok(link && link.href === 'https://rzp.io/i/abc123' && link.target === '_blank' && link.rel.includes('noopener'),
    'the outcome offers the payment page');
  card.querySelector('.fb-consent-deny').click();
  ok(!aw.shadowRoot.querySelector('.fb-action'), 'Close removes the card');

  // Over the voice socket a proposal arrives as an event; Cancel posts a cancel.
  aw.session.feed({ channel: 'EVENTS', type: 'action_proposal', payload: { id: 'run-2', kind: 'trial', label: 'Start a trial', summary: [] } });
  const c2 = aw.shadowRoot.querySelector('.fb-action');
  ok(c2 && c2.textContent.includes('Start a trial'), 'a socket proposal shows the card too');
  c2.querySelector('.fb-consent-deny').click();
  await settle();
  ok(posts.some((p) => p.u.endsWith('/actions/cancel') && p.body.run_id === 'run-2') && !aw.shadowRoot.querySelector('.fb-action'),
    'Cancel tells the server and closes');
  aw.remove();

  // A site's own component in a sandboxed iframe, and its message contract.
  const box = document.createElement('div');
  document.body.append(box);
  const reported = [];
  const ec = new Canvas(box, () => {}, (id, p) => reported.push(p));
  ec.add({ sync_id: 'ui_embed', component_type: 'embed', initial_state: { src: 'https://tools.acme.example/calc', name: 'plan_builder', props: { seats: 3 } } });
  await tick();
  const frame = box.querySelector('iframe');
  ok(frame && frame.getAttribute('sandbox') === 'allow-scripts' && frame.src === 'https://tools.acme.example/calc'
    && frame.getAttribute('referrerpolicy') === 'no-referrer', 'an embed is a scripts-only sandboxed iframe of the registered URL');
  const send = (data, source) => window.dispatchEvent(new window.MessageEvent('message', { data, source }));
  send({ type: 'fb:resize', height: 5000 }, frame.contentWindow);
  ok(frame.style.height === '800px', 'fb:resize is clamped (80–800 px)');
  send({ type: 'fb:state', state: { seats: 9 } }, frame.contentWindow);
  ok(reported.length === 1 && reported[0].state.seats === 9, 'fb:state reaches the agent');
  send({ type: 'fb:state', state: { blob: 'x'.repeat(3000) } }, frame.contentWindow);
  send({ type: 'fb:state', state: { seats: 1 } }, window);
  send({ type: 'navigate', url: 'https://evil.example' }, frame.contentWindow);
  ok(reported.length === 1, 'oversized state, other senders and unknown messages are ignored');
  ec.add({ sync_id: 'ui_bad', component_type: 'embed', initial_state: { src: 'javascript:alert(1)' } });
  ok(box.querySelectorAll('iframe').length === 1, 'a non-https embed draws nothing');
  box.remove();
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
