// Microphone consent (WS8). Before the first voice turn the visitor is told what
// listening means — audio is not stored, how long transcripts are kept, the
// site's privacy policy — and chooses to allow the mic or keep typing. The
// choice is remembered per site in this browser, and the server ignores mic
// audio until the widget reports it.

import { Privacy } from '../protocol';

/** Bump when the wording changes materially, so visitors are asked again. */
export const CONSENT_VERSION = '1';

const storageKey = (site: string) => `fluidbuddha:consent:${site}`;

export function hasConsent(site: string): boolean {
  try {
    return localStorage.getItem(storageKey(site)) === CONSENT_VERSION;
  } catch {
    return false;
  }
}

export function rememberConsent(site: string): void {
  try {
    localStorage.setItem(storageKey(site), CONSENT_VERSION);
  } catch {
    /* private mode: ask again next visit */
  }
}

function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
}

/** What the prompt says, from the site's privacy settings. */
export function consentCopy(p: Privacy, agentName = 'The assistant'): string {
  const parts = [
    `${agentName} listens through your microphone only while voice is on, to understand your questions.`,
    'Your audio is not stored.',
  ];
  if (p.redacts_pii) parts.push('Emails, phone and card numbers are masked before anything is saved.');
  if (p.retention_days && p.retention_days > 0)
    parts.push(`Transcripts are kept for ${p.retention_days} days to improve answers.`);
  else if (p.retention_days === 0) parts.push('Transcripts are kept to improve answers.');
  return parts.join(' ');
}

/** Show the consent dialog inside the widget's shadow root; resolves true when
 *  the visitor allows the microphone. */
export function consentPrompt(root: ShadowRoot, p: Privacy, agentName?: string): Promise<boolean> {
  return new Promise((resolve) => {
    const prev = root.activeElement as HTMLElement | null;
    const backdrop = document.createElement('div');
    backdrop.className = 'fb-consent';
    const card = document.createElement('div');
    card.className = 'fb-consent-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'fb-consent-title');

    const title = document.createElement('h2');
    title.id = 'fb-consent-title';
    title.textContent = 'Talk by voice?';
    const body = document.createElement('p');
    body.textContent = consentCopy(p, agentName);
    card.append(title, body);

    const policy = safeUrl(p.policy_url);
    if (policy) {
      const link = document.createElement('a');
      link.href = policy;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Privacy policy';
      card.append(link);
    }

    const actions = document.createElement('div');
    actions.className = 'fb-consent-actions';
    const deny = document.createElement('button');
    deny.type = 'button';
    deny.className = 'fb-consent-deny';
    deny.textContent = 'Type instead';
    const allow = document.createElement('button');
    allow.type = 'button';
    allow.className = 'fb-consent-allow';
    allow.textContent = 'Allow microphone';
    actions.append(deny, allow);
    card.append(actions);
    backdrop.append(card);

    const done = (ok: boolean) => {
      backdrop.remove();
      try {
        prev?.focus();
      } catch {
        /* noop */
      }
      resolve(ok);
    };
    allow.addEventListener('click', () => done(true));
    deny.addEventListener('click', () => done(false));
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) done(false);
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        done(false);
      } else if (e.key === 'Tab') {
        // Keep focus inside the dialog.
        const items = [...card.querySelectorAll<HTMLElement>('a, button')];
        const i = items.indexOf(root.activeElement as HTMLElement);
        const next = e.shiftKey ? (i <= 0 ? items.length - 1 : i - 1) : (i + 1) % items.length;
        e.preventDefault();
        items[next]?.focus();
      }
    });
    root.appendChild(backdrop);
    allow.focus();
  });
}
