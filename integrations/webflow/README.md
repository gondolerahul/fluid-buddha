# FluidBuddha on Webflow

1. In the FluidBuddha console, open your website → **Install** → **Webflow** and
   copy the snippet. It looks like:

   ```html
   <script src="https://<your-server>/widget/loader.js" data-key="fbk_…" async></script>
   ```

2. In Webflow, open **Site settings → Custom code**.
3. Paste the snippet into **Footer code** (before `</body>` tag).
4. **Save changes**, then **Publish** the site.

The agent appears on every page of the published site. (Webflow doesn't run custom
code in the Designer; check the published or staging `webflow.io` address.)

## Only some pages

Instead of Site settings, paste the snippet into a page's **Page settings → Custom
code → Before `</body>` tag**, for each page that should have the agent.

## Options

Add attributes to the snippet if you need them:

| Attribute | Values |
|---|---|
| `data-position` | `bottom-right` (default), `bottom-left` |
| `data-lang` | `en`, `hi` (Hindi must be on for the website in the console) |

Everything else — colour, greeting, design, knowledge, proactive messages — is set
in the FluidBuddha console and applies without republishing.

## Domain

In the console, set the website's domain to your Webflow domain (e.g.
`yoursite.webflow.io`) and your custom domain: the widget key only answers on that
domain and its subdomains.

Custom code needs a paid Webflow site plan.
