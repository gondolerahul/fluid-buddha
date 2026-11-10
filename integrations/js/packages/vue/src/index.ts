// @fluidbuddha/vue — the FluidBuddha agent in a Vue 3 app (M2-10).
//
//   <script setup>
//   import { FluidBuddha } from '@fluidbuddha/vue';
//   </script>
//   <FluidBuddha install-code="https://fbk_…@agent.example.com"
//                @navigate="(path) => router.push(path)" />
//
// Renders nothing in place: the widget floats over the page. Use it once, near
// the root; unmounting removes it.
import { defineComponent, h, onBeforeUnmount, onMounted, PropType, watch } from 'vue';
import {
  conversion,
  DesignLevel,
  FluidBuddhaHooks,
  Lang,
  mountWidget,
  NavigationMode,
  parseInstallCode,
  Position,
} from '../../../shared/loader';

export { conversion, parseInstallCode };
export type { DesignLevel, FluidBuddhaHooks, InstallTarget, Lang, NavigationMode, Position, WidgetOptions } from '../../../shared/loader';

type ScrollTarget = { sectionId?: string; direction?: string };

export const FluidBuddha = defineComponent({
  name: 'FluidBuddha',
  props: {
    /** From the console: your website → Install (`https://fbk_…@server`). */
    installCode: { type: String, required: true },
    /** Only if `installCode` is a bare widget key: the server's URL. */
    server: String,
    position: String as PropType<Position>,
    lang: String as PropType<Lang>,
    design: String as PropType<DesignLevel>,
    accent: String,
    greeting: String,
    autoStart: { type: Boolean, default: undefined },
    tour: { type: Boolean, default: undefined },
    navigation: String as PropType<NavigationMode>,
    // Declared as props (not emits) so the wrapper knows whether a listener is
    // attached: @navigate replaces the widget's own navigation.
    onNavigate: Function as PropType<(path: string) => void>,
    onScrollTo: Function as PropType<(target: ScrollTarget) => void>,
    onSetPersona: Function as PropType<(persona: string) => void>,
    onReady: Function as PropType<(el: HTMLElement) => void>,
    onError: Function as PropType<(err: Error) => void>,
  },
  setup(props) {
    let unmount: (() => void) | null = null;
    const mount = () => {
      unmount?.();
      const hooks: FluidBuddhaHooks = {};
      if (props.onNavigate) hooks.onNavigate = (path) => props.onNavigate?.(path);
      if (props.onScrollTo) hooks.onScrollTo = (t) => props.onScrollTo?.(t);
      if (props.onSetPersona) hooks.onSetPersona = (p) => props.onSetPersona?.(p);
      unmount = mountWidget({
        installCode: props.installCode,
        server: props.server,
        position: props.position,
        lang: props.lang,
        design: props.design,
        accent: props.accent,
        greeting: props.greeting,
        autoStart: props.autoStart,
        tour: props.tour,
        navigation: props.navigation,
        hooks,
        onReady: (el) => props.onReady?.(el),
        onError: (err) => (props.onError ? props.onError(err) : console.warn(err.message)),
      });
    };
    onMounted(mount);
    watch(
      () => [props.installCode, props.server, props.position, props.lang, props.design, props.accent,
        props.greeting, props.autoStart, props.tour, props.navigation,
        !!props.onNavigate, !!props.onScrollTo, !!props.onSetPersona],
      mount,
    );
    onBeforeUnmount(() => {
      unmount?.();
      unmount = null;
    });
    return () => null;
  },
});

/**
 * A generated region on your own page (Phase 1): FluidBuddha fills it for the
 * visitor's goal; until then (and if it can't) the slot content shows.
 *
 *   <FbRegion name="hero"><YourOwnHero /></FbRegion>
 *
 * Needs the widget on the page. Tell Vue that `fb-region` is a custom element
 * (compilerOptions.isCustomElement) if you also write it in templates directly.
 */
export const FbRegion = defineComponent({
  name: 'FbRegion',
  props: { name: { type: String, required: true } },
  setup(props, { slots }) {
    return () => h('fb-region', { name: props.name }, slots.default ? slots.default() : []);
  },
});

export default FluidBuddha;
