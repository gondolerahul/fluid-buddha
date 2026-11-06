// Just enough of Framer's API to typecheck integrations/framer/FluidBuddha.tsx.
declare module 'framer' {
  export const RenderTarget: { current(): string; canvas: string; preview: string; export: string; thumbnail: string };
  export const ControlType: { String: 'string'; Enum: 'enum'; Boolean: 'boolean'; Number: 'number' };
  export function addPropertyControls(component: unknown, controls: Record<string, Record<string, unknown>>): void;
}
