=== FluidBuddha AI Agent ===
Contributors: fluidbuddha
Tags: ai, chatbot, voice, sales, lead generation
Requires at least: 5.8
Tested up to: 6.8
Requires PHP: 7.4
Stable tag: 2.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

A voice and chat sales agent that answers your visitors from your own content, captures leads and books meetings.

== Description ==

FluidBuddha puts an AI agent on your site that visitors can talk to or type to. It answers from your own pages and documents, shows charts and comparisons when they help, and hands hot leads to your team.

This plugin adds the agent to your site. Everything else — what the agent knows, its voice, greeting, design, languages (English and Hindi), proactive messages and A/B tests — is set in the FluidBuddha console.

* One field to fill in: paste your install code.
* Never appears in wp-admin; hide it on any page (checkout, account…) with simple path patterns.
* Optionally hidden from your own logged-in team, so your visits don't count.
* Loads asynchronously in the footer, so it doesn't slow your pages down.

= External service =

This plugin connects to the FluidBuddha server named in your install code. On every public page it loads the agent's script from that server (`/widget/loader.js`), and the agent sends visitors' questions there to be answered. The settings page asks the server whether your key is valid (`/widget/config`). No data is sent until you enter an install code.

Visitors' microphone is only used after they agree to it. See FluidBuddha's terms and privacy policy for how conversations are handled.

== Installation ==

1. Install and activate the plugin.
2. In the FluidBuddha console, open your website → **Install** → **WordPress** and copy the install code.
3. In WordPress, go to **Settings → FluidBuddha**, paste the code and save.
4. Open your site: the agent appears in the corner.

== Frequently Asked Questions ==

= Where do I change the agent's colour, greeting or design? =

In the FluidBuddha console (your website → Settings). The plugin picks them up automatically.

= The settings page says the key isn't recognised. =

The key may have been rotated in the console. Copy the install code again.

= The agent doesn't appear on my site. =

Check that the page isn't in "Hide on these pages", that "Hide the agent from logged-in editors" is off (or log out), and that your website's domain in the console matches this site.

== Changelog ==

= 2.0.0 =
* Version aligned with FluidBuddha 2.0. No change to how the plugin works.

= 0.1.0 =
* First release.
