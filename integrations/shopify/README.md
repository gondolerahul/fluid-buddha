# FluidBuddha for Shopify

A Shopify app with one **theme app extension**: an app embed that adds the agent to
the storefront. No access scopes, no app backend, nothing stored in the shop.

## For merchants

1. Install the app.
2. **Online Store → Themes → Customize → App embeds** (the icon in the left bar).
3. Switch on **FluidBuddha agent** and paste the **install code** from the
   FluidBuddha console (your website → **Install** → **Shopify**).
4. Optionally pick the position, language, and whether it shows on the cart and
   customer account pages. **Save**.

In the console, set the website's domain to the shop's domain (and
`myshopify.com` address, for previews): the key only answers there.

The agent never appears in checkout (Shopify doesn't run theme code there).

## Development

Needs the Shopify CLI and a Partner account with a development store.

```bash
cd integrations/shopify
npm install
shopify app config link     # fills client_id in shopify.app.toml
shopify app dev             # preview on the development store
shopify app deploy          # release a version of the extension
```

`npm test` renders the embed with [LiquidJS](https://liquidjs.com) and checks the
install-code parsing, the page rules, the schema and its translations.

## Listing on the Shopify App Store

The listing needs an app URL and a privacy policy URL. With no access scopes and no
backend, `application_url` can point to a static page that explains how to switch
the embed on; replace the `example.com` placeholders in `shopify.app.toml` before
deploying.
