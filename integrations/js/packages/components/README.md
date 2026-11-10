# @fluidbuddha/components

Author the components FluidBuddha composes generated pages from, in React.

Generated pages draw your components as **Web Components** (the runtime contract):
the agent picks a component from your approved manifest, FluidBuddha binds its data,
and the widget creates your custom element with those props. This package turns a
React component into that custom element and writes its manifest entry from the same
declaration.

```bash
npm install @fluidbuddha/components react react-dom
```

```tsx
import { defineFbComponent } from '@fluidbuddha/components';

type Props = { title?: string; tiers: { name: string; price: string }[] };

function PlanTableView({ title, tiers }: Props) {
  return (
    <section>
      {title && <h2>{title}</h2>}
      {tiers.map((t) => <div key={t.name}>{t.name}: {t.price}</div>)}
    </section>
  );
}

export const PlanTable = defineFbComponent(PlanTableView, {
  id: 'acme.PlanTable',
  tag: 'acme-plan-table',
  purpose: 'Compare 2–4 subscription plans',
  useWhen: ['compare_plans'],
  props: {
    title: { type: 'string', source: 'model_text', maxLength: 120 },
    // Only live data from your API, never typed by the model:
    tiers: { type: 'array', source: 'binding_only', required: true, maxItems: 4 },
  },
  styles: ':host { display: block; }',
});
```

Build these into one browser bundle (any bundler, React included or loaded first), host
it on https, then generate the manifest with the bundle's integrity hash:

```bash
npx fb-manifest --module ./dist/fb-components.js \
  --bundle-file ./dist/fb-components.js \
  --bundle-url https://cdn.example.com/fb-components.js > manifest.json
```

Paste `manifest.json` into the console (**Components → New draft**) and have an Admin
approve it. The widget loads the bundle with subresource integrity, so a changed file
is refused until you approve a manifest with its new hash.

- Props are set as element **properties**, so arrays and objects arrive intact.
- `source` says who may fill a prop: `model_text` (the agent's copy), `binding_only`
  (your API data only), or `either`.
- Tags must contain a dash and may not start with `fluid-buddha` or `fb-`.
