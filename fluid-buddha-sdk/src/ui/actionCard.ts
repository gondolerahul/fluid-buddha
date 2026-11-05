// An action the agent proposes (M2-8): a payment link, a quote, a trial…
// Nothing happens until the visitor presses Confirm here. The card then shows
// the outcome — a message and, when there is one, a link to open (the
// payment page, the trial's login, the booking page). Styled like the
// microphone consent dialog, so it sits above every design level.

import { t } from '../i18n';

export interface ActionCard {
  id: string;
  kind: string;
  label: string;
  summary: { label: string; value: string }[];
}

export interface ActionOutcome {
  status: string;
  message?: string | null;
  url?: string | null;
  error?: string | null;
}

/** Show `card`; `answer(true)` confirms (resolving with the outcome),
 *  `answer(false)` cancels. */
export function actionPrompt(
  root: ShadowRoot,
  card: ActionCard,
  answer: (confirm: boolean) => Promise<ActionOutcome | null>,
): void {
  const el = (tag: string, cls?: string, text?: string) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const backdrop = el('div', 'fb-consent fb-action');
  const box = el('div', 'fb-consent-card');
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.setAttribute('aria-label', card.label);
  const rows = el('dl', 'fb-action-rows');
  card.summary.forEach((r) => rows.append(el('dt', undefined, r.label), el('dd', undefined, r.value)));
  const note = el('p', undefined, t('actionNote'));
  const buttons = el('div', 'fb-consent-actions');
  const cancel = el('button', 'fb-consent-deny', t('cancel')) as HTMLButtonElement;
  const ok = el('button', 'fb-consent-allow', t('confirm')) as HTMLButtonElement;
  cancel.type = ok.type = 'button';
  buttons.append(cancel, ok);
  box.append(el('h2', undefined, card.label), rows, note, buttons);
  backdrop.append(box);
  root.append(backdrop);
  ok.focus();

  const close = () => backdrop.remove();
  cancel.addEventListener('click', () => {
    close();
    void answer(false);
  });
  ok.addEventListener('click', async () => {
    ok.disabled = cancel.disabled = true;
    ok.textContent = t('working');
    const out = await answer(true);
    const done = !!out && (out.status === 'done' || out.status === 'paid');
    note.textContent = done ? out!.message || t('actionDone') : out?.error || t('actionFailed');
    buttons.replaceChildren();
    if (done && out!.url && /^https:\/\//.test(out!.url)) {
      const a = el('a', 'fb-consent-allow', card.kind === 'payment_link' ? t('payNow') : t('openLink')) as HTMLAnchorElement;
      a.href = out!.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      buttons.append(a);
    }
    const shut = el('button', 'fb-consent-deny', t('close')) as HTMLButtonElement;
    shut.type = 'button';
    shut.addEventListener('click', close);
    buttons.prepend(shut);
  });
}
