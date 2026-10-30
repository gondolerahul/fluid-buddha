// Fetches a site's brand tokens from the backend (Extreme intelligence) and
// applies them as CSS custom properties, so runtime-generated pages are themed
// with the owner's colours/typography rather than the SDK defaults.

export interface DesignSystemDoc {
  name: string;
  logo_url: string;
  colors: Record<string, string>;
  typography: Record<string, unknown>;
  radius: string;
  brand_voice: string;
  tokens: Record<string, string>;
}

export async function fetchDesignSystem(api: string, site: string): Promise<DesignSystemDoc | null> {
  if (!api) return null;
  try {
    const res = await fetch(
      `${api.replace(/\/$/, '')}/design-system?site=${encodeURIComponent(site)}`,
    );
    if (!res.ok) return null;
    return (await res.json()) as DesignSystemDoc;
  } catch {
    return null;
  }
}

/** Apply `--ds-*` tokens (and a couple of derived aliases) to an element. */
export function applyTokens(el: HTMLElement, tokens: Record<string, string> | undefined): void {
  if (!tokens) return;
  for (const [k, v] of Object.entries(tokens)) {
    if (k.startsWith('--ds-')) el.style.setProperty(k, v);
  }
}
