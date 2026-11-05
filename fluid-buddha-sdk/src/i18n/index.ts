// The widget's words in English and Hindi (M2-7).
//
// One table per language with the same keys (the SDK test checks that every
// English string has a Hindi one with the same {placeholders}). `t()` reads
// the widget's current language, set once when the widget starts from the
// embed's `data-lang`, the site's settings and the visitor's browser.
//
// The Hindi table (hi.ts) is fetched only for a Hindi visitor (prepareLang).

import { loadHindi } from './load';

const en = {
  greeting:
    "Hi, I'm Pragya. Tap the mic and ask me anything — I can show you around, run the numbers, and answer with grounded facts.",
  talkTo: 'Talk to {name}',
  messageTo: 'Message {name}',
  close: 'Close',
  send: 'Send',
  toggleVoice: 'Toggle voice',
  voiceTitle: 'Hold a conversation by voice',
  placeholder: 'Speak, or type a question…',
  askAnything: 'Ask {name} anything — or just speak…',
  ask: 'Ask {name}',
  summon: 'Summon {name}',
  awaken: 'Awaken {name} and start talking',
  openAgent: 'Open {name}',
  tapAwaken: 'tap to awaken',
  tapTalk: 'tap to talk',
  pressKey: 'press {key} anytime · or speak',
  isThinking: '{name} is thinking',
  chipPricing: 'Show me pricing',
  chipIntegrate: 'How do you integrate?',
  chipTour: 'Give me a quick tour',
  online: 'online',
  voiceReady: 'voice ready',
  textMode: 'text mode',
  listening: 'listening',
  thinking: 'thinking',
  speaking: 'speaking',
  guidedTour: 'guided tour',
  consentTitle: 'Talk by voice?',
  consentListens: '{name} listens through your microphone only while voice is on, to understand your questions.',
  consentNoAudio: 'Your audio is not stored.',
  consentMasked: 'Emails, phone and card numbers are masked before anything is saved.',
  consentKeptDays: 'Transcripts are kept for {days} days to improve answers.',
  consentKept: 'Transcripts are kept to improve answers.',
  privacyPolicy: 'Privacy policy',
  typeInstead: 'Type instead',
  allowMic: 'Allow microphone',
  theAssistant: 'The assistant',
  callTitle: 'Talk with {name}?',
  callBody:
    '{name} from the team would like to talk with you by voice, in your browser. The call uses your microphone and is not recorded.',
  notNow: 'Not now',
  acceptCall: 'Accept call',
  onCall: 'On a call with {name}',
  hangUp: 'Hang up',
  sources: 'Sources',
  grounded: 'Grounded',
  groundedMatch: 'grounded · {pct}% match',
  joined: '{name} from the team joined the conversation.',
  handedBack: '{name} handed you back to the assistant.',
  endedCall: '{name} ended the call.',
  callFailed: 'The call could not connect.',
  micForCall: 'Your microphone is not available for the call.',
  someoneTeam: 'Someone from the team',
  team: 'Team',
  dismiss: 'Dismiss',
  voiceUnavailable: 'Voice link unavailable — using text mode.',
  recalibrating: 'Re-calibrating…',
  error: 'Error',
  voiceOff: 'Voice is off — type to chat instead.',
  micUnavailable: 'Microphone unavailable — type to chat instead.',
  offline: 'Agent is offline right now. Please try again shortly.',
  connError: 'Connection error. The agent is offline.',
  recapFirst: 'Ask me something first, then I can put together a recap.',
  recapBadEmail: "That email address doesn't look right.",
  recapReady: "Here's your recap. Open it on any device or forward it to your team: {url}",
  recapEmailed: " I've also emailed it to {email}.",
  recapFailed: "I couldn't make a recap just now. Please try again in a moment.",
  thanks: 'Thanks — the team will be in touch soon.',
  sendFailed: "Couldn't send that just now. Please try again.",
  submit: 'Submit',
  sending: 'Sending…',
  sent: 'Sent ✓',
  tryAgain: 'Try again',
  confirm: 'Confirm',
  cancel: 'Cancel',
  working: 'Working…',
  actionNote: 'Nothing happens until you confirm.',
  actionDone: 'Done.',
  actionFailed: "That didn't work. Please try again.",
  payNow: 'Open payment page',
  openLink: 'Open',
};

export type StringKey = keyof typeof en;
export type Lang = 'en' | 'hi';



/** The tables loaded so far (Hindi arrives with prepareLang('hi')). Exported
 *  for the string-coverage test. */
export const STRINGS: { en: Record<StringKey, string>; hi?: Record<StringKey, string> } = { en };

let current: Lang = 'en';

export function setLang(lang: Lang): void {
  current = lang === 'hi' && STRINGS.hi ? 'hi' : 'en';
}

/** Make `lang` the widget's language, fetching its table first if needed.
 *  Resolves with the language actually set: English if Hindi can't load. */
export async function prepareLang(lang: Lang): Promise<Lang> {
  if (lang === 'hi' && !STRINGS.hi) {
    try {
      STRINGS.hi = await Promise.race([
        loadHindi(),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
      ]);
    } catch {
      /* stay in English */
    }
  }
  setLang(lang);
  return current;
}

export function getLang(): Lang {
  return current;
}

/** The current language's text for `key`, with {placeholders} filled in. */
export function t(key: StringKey, vars?: Record<string, string | number>): string {
  const s = (current === 'hi' && STRINGS.hi?.[key]) || en[key];
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;
}

/** The site's language settings, as the server sends them (M2-7). */
export interface SiteLanguages {
  languages?: string[] | null;
  widget_language?: string | null;
}

/** Which language the widget shows: the embed's `data-lang` if the site
 *  allows it, else the site's setting, else (on `auto`) the browser's. A site
 *  that hasn't switched Hindi on is English; without site settings (no key)
 *  only an explicit `data-lang` chooses. */
export function pickLang(wanted: string | undefined, site?: SiteLanguages | null): Lang {
  const known = !!(site && site.languages);
  const allowsHindi = known ? (site!.languages as string[]).includes('hi') : true;
  if (wanted === 'en' || wanted === 'hi') return wanted === 'hi' && !allowsHindi ? 'en' : wanted;
  if (!known || !allowsHindi) return 'en';
  if (site!.widget_language === 'en' || site!.widget_language === 'hi') return site!.widget_language;
  const nav = typeof navigator !== 'undefined' ? navigator.languages || [navigator.language] : [];
  return nav.some((l) => /^hi(\b|-)/i.test(l || '')) ? 'hi' : 'en';
}
