// The proactive nudge (M2-3): a short message bubble next to the launcher.
// Clicking it opens the conversation; × dismisses it (and silences triggers
// for the rest of the visit). It never moves focus or plays sound.

import { t } from '../i18n';

export function showNudge(root: ShadowRoot, message: string, onOpen: () => void,
                          onDismiss: () => void): () => void {
  root.querySelector('.fb-nudge')?.remove();
  const box = document.createElement('div');
  box.className = 'fb-nudge';
  box.setAttribute('role', 'status');
  const open = document.createElement('button');
  open.type = 'button';
  open.className = 'fb-nudge-msg';
  open.textContent = message;
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'fb-nudge-x';
  close.setAttribute('aria-label', t('dismiss'));
  close.textContent = '×';
  box.append(open, close);
  const remove = () => box.remove();
  open.addEventListener('click', () => { remove(); onOpen(); });
  close.addEventListener('click', () => { remove(); onDismiss(); });
  root.appendChild(box);
  return remove;
}
