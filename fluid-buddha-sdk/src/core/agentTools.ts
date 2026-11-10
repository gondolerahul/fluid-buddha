// Page-declared tools (generative experience Phase 5, strategy §6.5).
//
// When the browser offers an in-page agent API (`navigator.modelContext`, the
// emerging "WebMCP" proposal), a served page registers its tools so the
// browser's assistant can use the page the way a person would:
//
//   * read_view       — the page as text (headings, sections, and the step it is on);
//   * <action id>     — one per action on the page (data-fb-action): brings that
//                       control into view and focuses it. It never presses it: the
//                       person still decides.
//
// Feature-detected and silent: without the API nothing happens.

interface ToolDef {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  annotations?: Record<string, unknown>;
  execute: (args: Record<string, unknown>) => Promise<{ content: { type: 'text'; text: string }[] }>;
}

interface ModelContext {
  registerTool?: (tool: ToolDef) => unknown;
  provideContext?: (ctx: { tools: ToolDef[] }) => unknown;
}

const text = (t: string) => ({ content: [{ type: 'text' as const, text: t }] });

/** The page's text as an agent should read it (visible step only when stepped). */
export function viewText(root: Element): string {
  const lines: string[] = [];
  const title = root.ownerDocument.title;
  if (title) lines.push(`# ${title}`, '');
  const steps = Array.from(root.querySelectorAll('.fb-steps li'));
  if (steps.length) {
    const cur = steps.find((li) => li.getAttribute('aria-current') === 'step');
    lines.push(`Steps: ${steps.map((li) => (li === cur ? `[${li.textContent}]` : li.textContent)).join(' → ')}`, '');
  }
  for (const s of Array.from(root.querySelectorAll<HTMLElement>('[data-fb-region]'))) {
    if (s.hidden) continue;
    const t = (s.innerText || s.textContent || '').replace(/\n{3,}/g, '\n\n').trim();
    if (t) lines.push(t, '');
  }
  const actions = Array.from(root.querySelectorAll('[data-fb-action]'))
    .map((el) => `- ${el.getAttribute('data-fb-action')}: ${(el.textContent || '').trim()}`);
  if (actions.length) lines.push('Actions on this page (a person presses them):', ...actions);
  return lines.join('\n').trim();
}

const SAFE_NAME = /^[a-z][a-z0-9_]{0,40}$/;

/** Register the page's tools with an in-browser agent; returns how many. */
export function declareTools(root: Element, nav: Navigator = navigator): number {
  const mc = (nav as Navigator & { modelContext?: ModelContext }).modelContext;
  if (!mc || (!mc.registerTool && !mc.provideContext)) return 0;
  const tools: ToolDef[] = [{
    name: 'read_view',
    description: 'Read this page: its sections, the step it is on, and the actions it offers.',
    inputSchema: { type: 'object', properties: {} },
    annotations: { readOnlyHint: true },
    execute: async () => text(viewText(root)),
  }];
  const seen = new Set<string>();
  for (const el of Array.from(root.querySelectorAll<HTMLElement>('[data-fb-action]'))) {
    const id = el.getAttribute('data-fb-action') || '';
    if (!SAFE_NAME.test(id) || seen.has(id) || id === 'read_view') continue;
    seen.add(id);
    const label = (el.textContent || id).trim().slice(0, 80);
    tools.push({
      name: id,
      description: `Show the person the "${label}" control on this page and focus it. It does not press it.`,
      inputSchema: { type: 'object', properties: {} },
      execute: async () => {
        const step = el.closest<HTMLElement>('[data-fb-step]');
        if (step?.hidden) {
          root.querySelector<HTMLElement>(`[data-fb-step-nav="${step.getAttribute('data-fb-step')}"]`)?.click();
        }
        el.scrollIntoView?.({ block: 'center' });
        el.focus?.();
        return text(`The "${label}" control is in view and focused. Ask the person to press it.`);
      },
    });
  }
  try {
    if (mc.registerTool) tools.forEach((t) => mc.registerTool!(t));
    else mc.provideContext!({ tools });
  } catch {
    return 0;
  }
  return tools.length;
}
