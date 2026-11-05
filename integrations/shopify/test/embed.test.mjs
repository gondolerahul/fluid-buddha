// Renders the app embed with liquidjs (same core filters as Shopify's Liquid)
// and checks its schema and translations. Run: npm test
import { Liquid } from 'liquidjs';
import { readFileSync } from 'node:fs';

const ROOT = new URL('../extensions/fluidbuddha-embed/', import.meta.url);
const source = readFileSync(new URL('blocks/fluidbuddha.liquid', ROOT), 'utf8');
const schemaMatch = /{%\s*schema\s*%}([\s\S]*?){%\s*endschema\s*%}/.exec(source);
const template = source.replace(schemaMatch[0], '');
const engine = new Liquid();

let failures = 0;
const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`); if (!cond) failures++; };

const defaults = { install_code: '', position: 'default', lang: 'auto', show_on_cart: true, show_on_account: false };
const render = (settings, request = {}) => engine.parseAndRender(template, {
  block: { settings: { ...defaults, ...settings } },
  request: { page_type: 'index', design_mode: false, ...request },
});
const scriptOf = (html) => /<script\s+src="([^"]*)"([^>]*)>/.exec(html);

{
  const html = await render({ install_code: ' https://fbk_abcdefgh12345678@agent.example.com/ ' });
  const m = scriptOf(html);
  ok(!!m && m[1] === 'https://agent.example.com/widget/loader.js', 'adds the loader from the install code server');
  ok(m && m[2].includes('data-key="fbk_abcdefgh12345678"'), 'with the widget key');
  ok(m && m[2].includes('async'), 'loaded async');
  ok(m && !m[2].includes('data-position') && !m[2].includes('data-lang'), 'defaults add nothing else');
  ok(html.includes('<link rel="preconnect" href="https://agent.example.com"'), 'preconnects to the server');
}
{
  const m = scriptOf(await render({ install_code: 'http://fbk_abcdefgh12345678@localhost:8081/fb', position: 'bottom-left', lang: 'hi' }));
  ok(m && m[1] === 'http://localhost:8081/fb/widget/loader.js', 'keeps port and path');
  ok(m && m[2].includes('data-position="bottom-left"') && m[2].includes('data-lang="hi"'), 'passes position and language');
}
for (const bad of ['', 'fbk_abcdefgh12345678', 'https://agent.example.com', 'https://nokey@agent.example.com',
  'javascript://fbk_abcdefgh12345678@x', 'https://fbk_abcdefgh12345678@agent.example.com/"><script>alert(1)</script>',
  'https://fbk_abcdefgh12345678@a.example.com?x=1', 'https://fbk_a@b@c.example.com']) {
  const html = await render({ install_code: bad });
  ok(!scriptOf(html) && !html.includes('alert(1)'), `refused: ${bad || '(empty)'}`);
}
{
  const html = await render({ install_code: 'nonsense' }, { design_mode: true });
  ok(html.includes('console.warn') && !scriptOf(html), 'the theme editor warns about a bad code');
}
{
  const code = 'https://fbk_abcdefgh12345678@agent.example.com';
  ok(!!scriptOf(await render({ install_code: code }, { page_type: 'cart' })), 'shows on the cart by default');
  ok(!scriptOf(await render({ install_code: code, show_on_cart: false }, { page_type: 'cart' })), 'can be hidden on the cart');
  ok(!scriptOf(await render({ install_code: code }, { page_type: 'customers/account' })), 'hidden on account pages by default');
  ok(!!scriptOf(await render({ install_code: code, show_on_account: true }, { page_type: 'customers/order' })), 'can show on account pages');
  ok(!!scriptOf(await render({ install_code: code }, { page_type: 'product' })), 'shows on product pages');
}

// Schema and translations.
const schema = JSON.parse(schemaMatch[1]);
ok(schema.target === 'body', 'app embed targets the body');
const ids = schema.settings.map((s) => s.id);
ok(new Set(ids).size === ids.length, 'setting ids are unique');
ok(ids.join() === Object.keys(defaults).join(), 'the test covers every setting');
const locale = JSON.parse(readFileSync(new URL('locales/en.default.json', ROOT), 'utf8'));
const lookup = (path) => path.split('.').reduce((o, k) => (o ? o[k] : undefined), locale);
const keys = JSON.stringify(schema).match(/"t:[^"]+"/g).map((k) => k.slice(3, -1));
ok(keys.every((k) => typeof lookup(k) === 'string'), 'every t: label has an English translation');

console.log(failures ? `\n${failures} FAILED` : '\nALL PASS');
process.exit(failures ? 1 : 0);
