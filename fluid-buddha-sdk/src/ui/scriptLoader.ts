// For the <script>-tag build: an IIFE can't split chunks, so parts loaded on
// demand (the Level 2 particle field, the component renderers) ship as their
// own .global.js files next to fluid-buddha.global.js and are fetched from
// there with a script tag.

// Resolved while the core script runs, when currentScript still points at it.
const baseUrl = ((): string => {
  if (typeof document === 'undefined') return '';
  const own = document.currentScript as HTMLScriptElement | null;
  return (
    own?.src ||
    document.querySelector<HTMLScriptElement>('script[src*="fluid-buddha"][src$=".global.js"]')?.src ||
    ''
  );
})();

const pending: Record<string, Promise<unknown> | undefined> = {};

/** Load `file` (next to the core script) once; resolves with `window[name]`. */
export function loadGlobal<T>(file: string, name: string): Promise<T> {
  const w = window as unknown as Record<string, T | undefined>;
  if (w[name]) return Promise.resolve(w[name] as T);
  const p =
    (pending[name] as Promise<T> | undefined) ||
    new Promise<T>((resolve, reject) => {
      if (!baseUrl) {
        reject(new Error(`fluid-buddha: cannot locate ${file}`));
        return;
      }
      const s = document.createElement('script');
      s.src = new URL(file, baseUrl).href;
      s.async = true;
      s.onload = () => (w[name] ? resolve(w[name] as T) : reject(new Error(`fluid-buddha: ${file} did not register`)));
      s.onerror = () => reject(new Error(`fluid-buddha: failed to load ${s.src}`));
      document.head.appendChild(s);
    }).catch((err) => {
      pending[name] = undefined; // allow a retry
      throw err;
    });
  pending[name] = p;
  return p;
}
