// Bundles a tiny React app using @fluidbuddha/react for fluid-buddha-sdk/demo/install.html?mode=react.
//   node demo/react-demo.mjs   →  ../../fluid-buddha-sdk/dist/integrations-react-demo.js
import { build } from 'esbuild';

await build({
  stdin: {
    contents: `
      import { createElement as h, useState } from 'react';
      import { createRoot } from 'react-dom/client';
      import { FluidBuddha } from '@fluidbuddha/react';
      function App() {
        const [route, setRoute] = useState('/');
        return h('div', { style: { position: 'fixed', top: 12, right: 12, padding: '8px 12px', background: '#fff', border: '1px solid #ddd', borderRadius: 8 } },
          'React app · route: ', h('b', { id: 'route' }, route),
          h(FluidBuddha, { installCode: window.__installCode, onNavigate: setRoute,
            onReady: () => { document.getElementById('status').textContent = 'Mounted by @fluidbuddha/react.'; } }));
      }
      const el = document.createElement('div');
      document.body.appendChild(el);
      createRoot(el).render(h(App));
    `,
    resolveDir: process.cwd(),
    loader: 'js',
  },
  bundle: true,
  minify: true,
  define: { 'process.env.NODE_ENV': '"production"' },
  outfile: '../../fluid-buddha-sdk/dist/integrations-react-demo.js',
  logLevel: 'info',
});
