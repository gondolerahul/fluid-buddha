// @fluidbuddha/react — the FluidBuddha agent in a React app (M2-10).
//
//   import { FluidBuddha } from '@fluidbuddha/react';
//   <FluidBuddha installCode="https://fbk_…@agent.example.com"
//                onNavigate={(path) => navigate(path)} />
//
// Renders nothing in place: the widget floats over the page. Mount it once,
// near the root; unmounting removes it.
import { useEffect, useRef } from 'react';
import {
  conversion,
  FluidBuddhaHooks,
  mountWidget,
  parseInstallCode,
  WidgetOptions,
} from '../../../shared/loader';

export { conversion, parseInstallCode };
export type { DesignLevel, FluidBuddhaHooks, InstallTarget, Lang, NavigationMode, Position, WidgetOptions } from '../../../shared/loader';

export interface FluidBuddhaProps extends WidgetOptions {
  /** From the console: your website → Install (`https://fbk_…@server`). */
  installCode: string;
  /** Only if `installCode` is a bare widget key: the FluidBuddha server's URL. */
  server?: string;
  /** Route inside your app (React Router, Next.js…) instead of a page load. */
  onNavigate?: (path: string) => void;
  onScrollTo?: (target: { sectionId?: string; direction?: string }) => void;
  onSetPersona?: (persona: string) => void;
  /** The widget element, once it's on the page. */
  onReady?: (el: HTMLElement) => void;
  onError?: (err: Error) => void;
}

export function FluidBuddha(props: FluidBuddhaProps): null {
  // Callbacks are read through a ref, so passing new functions on each render
  // doesn't recreate the widget (and drop the conversation).
  const latest = useRef(props);
  latest.current = props;
  const { installCode, server, position, lang, design, accent, greeting, autoStart, tour, navigation } = props;
  // Whether a hook is given changes the widget's behaviour (onNavigate replaces
  // its own navigation), so that — not the function itself — is a dependency.
  const has = [!!props.onNavigate, !!props.onScrollTo, !!props.onSetPersona].join();

  useEffect(() => {
    const hooks: FluidBuddhaHooks = {};
    const p = latest.current;
    if (p.onNavigate) hooks.onNavigate = (path) => latest.current.onNavigate?.(path);
    if (p.onScrollTo) hooks.onScrollTo = (t) => latest.current.onScrollTo?.(t);
    if (p.onSetPersona) hooks.onSetPersona = (persona) => latest.current.onSetPersona?.(persona);
    return mountWidget({
      installCode, server, position, lang, design, accent, greeting, autoStart, tour, navigation,
      hooks,
      onReady: (el) => latest.current.onReady?.(el),
      onError: (err) => (latest.current.onError ? latest.current.onError(err) : console.warn(err.message)),
    });
  }, [installCode, server, position, lang, design, accent, greeting, autoStart, tour, navigation, has]);

  return null;
}

export default FluidBuddha;
