# @fluidbuddha/vue

The FluidBuddha voice and chat agent as a Vue 3 component.

```bash
npm install @fluidbuddha/vue
```

```vue
<script setup lang="ts">
import { FluidBuddha } from '@fluidbuddha/vue';
import { useRouter } from 'vue-router';
const router = useRouter();
</script>

<template>
  <RouterView />
  <FluidBuddha
    install-code="https://fbk_…@agent.example.com"
    @navigate="(path) => router.push(path)"
  />
</template>
```

Copy the **install code** from the FluidBuddha console: your website → **Install** → Vue.
It holds your widget key and the FluidBuddha server address.

The component renders nothing in place: the agent floats over the page. Use it
once, near the root (e.g. in `App.vue`). Unmounting it removes the agent.

The agent's code isn't bundled into your app; it loads from the FluidBuddha
server when the component mounts.

## Props and events

| Prop | Type | Notes |
|---|---|---|
| `install-code` | `string` | Required. `https://fbk_…@server`, from the console. |
| `server` | `string` | Only if `install-code` is a bare `fbk_…` key. |
| `position` | `'bottom-right' \| 'bottom-left'` | |
| `lang` | `'auto' \| 'en' \| 'hi'` | Hindi needs Hindi switched on for the website. |
| `design` | `'level1' \| 'level2' \| 'level3'` | Leave out to use the website's setting (and A/B tests). |
| `accent` | `string` | Hex colour; leave out to use the website's. |
| `greeting`, `auto-start`, `tour`, `navigation` | | As in the widget. |

| Event | Payload | Notes |
|---|---|---|
| `@navigate` | `path` | Route inside your app instead of a page load. |
| `@scroll-to` | `{ sectionId, direction }` | Handle scrolling yourself. |
| `@set-persona` | `persona` | Switch your site's persona/theme. |
| `@ready` | the widget element | |
| `@error` | `Error` | Bad install code, server unreachable. Default: a console warning. |

Options you leave out come from the website's settings in the console.

## Goals for A/B tests

```ts
import { conversion } from '@fluidbuddha/vue';
conversion('demo_booked');
```

## Nuxt

Wrap it in `<ClientOnly>`; it does nothing during server rendering.
