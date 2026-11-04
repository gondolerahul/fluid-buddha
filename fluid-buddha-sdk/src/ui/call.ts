// Voice calls with a person from the site's team (M2-2): the "accept this call?"
// dialog (styled like the microphone consent) and the bar shown during a call.

/** Ask the visitor to accept a call from `name`; resolves true to accept. */
export function callPrompt(root: ShadowRoot, name: string): Promise<boolean> {
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'fb-consent';
    const card = document.createElement('div');
    card.className = 'fb-consent-card';
    card.setAttribute('role', 'alertdialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'fb-call-title');
    const title = document.createElement('h2');
    title.id = 'fb-call-title';
    title.textContent = `Talk with ${name}?`;
    const body = document.createElement('p');
    body.textContent = `${name} from the team would like to talk with you by voice, in your browser. ` +
      'The call uses your microphone and is not recorded.';
    const actions = document.createElement('div');
    actions.className = 'fb-consent-actions';
    const no = document.createElement('button');
    no.type = 'button';
    no.className = 'fb-consent-deny';
    no.textContent = 'Not now';
    const yes = document.createElement('button');
    yes.type = 'button';
    yes.className = 'fb-consent-allow';
    yes.textContent = 'Accept call';
    actions.append(no, yes);
    card.append(title, body, actions);
    backdrop.append(card);
    const done = (ok: boolean) => {
      backdrop.remove();
      resolve(ok);
    };
    yes.addEventListener('click', () => done(true));
    no.addEventListener('click', () => done(false));
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') done(false);
    });
    root.appendChild(backdrop);
    yes.focus();
  });
}

/** Shows (or removes) the in-call bar with a hang-up button. */
export function callBar(root: ShadowRoot): (active: boolean, name: string, hangup: () => void) => void {
  let bar: HTMLDivElement | null = null;
  return (active, name, hangup) => {
    bar?.remove();
    bar = null;
    if (!active) return;
    bar = document.createElement('div');
    bar.className = 'fb-callbar';
    bar.setAttribute('role', 'status');
    const label = document.createElement('span');
    label.textContent = `On a call with ${name}`;
    const end = document.createElement('button');
    end.type = 'button';
    end.textContent = 'Hang up';
    end.addEventListener('click', () => hangup());
    bar.append(label, end);
    root.appendChild(bar);
  };
}
