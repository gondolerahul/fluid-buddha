# @fluidbuddha/react

The FluidBuddha voice and chat agent as a React component.

```bash
npm install @fluidbuddha/react
```

```tsx
import { FluidBuddha } from '@fluidbuddha/react';
import { useNavigate } from 'react-router-dom';

export function App() {
  const navigate = useNavigate();
  return (
    <>
      <Routes>…</Routes>
      <FluidBuddha
        installCode="https://fbk_…@agent.example.com"
        onNavigate={(path) => navigate(path)}
      />
    </>
  );
}
```

Copy the **install code** from the FluidBuddha console: your website → **Install** → React.
It holds your widget key and the FluidBuddha server address.

The component renders nothing in place: the agent floats over the page. Mount it
once, near the root of the app. Unmounting it removes the agent.

The agent's code isn't bundled into your app. It loads from the FluidBuddha
server when the component mounts, so visitors always get the current version and
your bundle grows by under 2 kB gzipped.

## Props

| Prop | Type | Notes |
|---|---|---|
| `installCode` | `string` | Required. `https://fbk_…@server`, from the console. |
| `server` | `string` | Only if `installCode` is a bare `fbk_…` key. |
| `position` | `'bottom-right' \| 'bottom-left'` | |
| `lang` | `'auto' \| 'en' \| 'hi'` | Hindi needs Hindi switched on for the website. |
| `design` | `'level1' \| 'level2' \| 'level3'` | Leave out to use the website's setting (and A/B tests). |
| `accent` | `string` | Hex colour; leave out to use the website's. |
| `greeting`, `autoStart`, `tour`, `navigation` | | As in the widget. |
| `onNavigate` | `(path) => void` | Route inside your app instead of a page load. |
| `onScrollTo` | `({ sectionId, direction }) => void` | Handle scrolling yourself. |
| `onSetPersona` | `(persona) => void` | Switch your site's persona/theme. |
| `onReady` | `(el) => void` | The widget element, once on the page. |
| `onError` | `(err) => void` | Bad install code, server unreachable. Default: a console warning. |

Options you leave out come from the website's settings in the console.

## Goals for A/B tests

```ts
import { conversion } from '@fluidbuddha/react';
conversion('demo_booked');
```

## Next.js

Use it in a client component (`'use client'`). It does nothing during server
rendering.
