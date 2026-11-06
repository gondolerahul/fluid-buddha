# FluidBuddha for WordPress

The plugin is in [`fluidbuddha/`](fluidbuddha) (WordPress.org layout, with
`readme.txt`). It adds one settings page, **Settings → FluidBuddha**, where the site
owner pastes the install code from the console. Options: position, widget language,
pages to hide it on (path patterns), and hiding it from logged-in editors.

What it does on the site: enqueues `<server>/widget/loader.js` (async, in the footer)
with the widget key on public pages only — never in wp-admin, feeds, AJAX or the
customizer — plus a `preconnect` to the server. The settings page checks the key
against the server (`/widget/config`, no agent turn).

## Try it locally

```bash
cd integrations/wordpress
docker compose up -d          # WordPress on http://localhost:8090 with the plugin mounted
```

Finish the WordPress install in the browser, activate **FluidBuddha AI Agent**, and
paste an install code from your local console (e.g.
`http://fbk_…@localhost:8081`). Two local-only wrinkles:

- Add `http://localhost:8090` to the backend's `CORS_ORIGINS`, or the widget's calls
  are refused (production runs with `CORS_ORIGINS=*`).
- The settings page's connection check runs inside the WordPress container, where
  `localhost` isn't your machine, so it reports "Can't reach the server". The widget
  itself loads in your browser and works.

## Tests

```bash
php tests/test-functions.php                 # install-code parsing, page rules, tag attributes
for f in fluidbuddha/*.php fluidbuddha/includes/*.php; do php -l "$f"; done
```

(CI runs both in a `php` container.)

## Publishing to WordPress.org

Zip the `fluidbuddha/` folder and submit it at wordpress.org/plugins/developers/add.
WordPress.org requires a GPL-compatible licence (the plugin header says
GPL-2.0-or-later) and the "External service" section in `readme.txt`, which is
already there.
