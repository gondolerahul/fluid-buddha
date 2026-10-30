---
name: framer-motion
description: Production patterns for Motion (framer-motion v12, imported from `motion/react`) — scroll-scrubbed animation, motion values, springs, reveal staggers, and the performance rules that keep it at 60fps. Use when building scroll-driven or interactive motion in React/Next.
source_note: >
  The repo originally requested (carlosverasteguii/daticket .codex/skills/framer-motion)
  ships a SKILL.md whose body is the literal string "404: Not Found" — a broken upstream
  stub. This file is a real replacement written for this project, which already depends on
  framer-motion ^12.40.0.
---

# Motion (framer-motion v12)

> Import from `motion/react` in new code (`import { motion, useScroll } from 'motion/react'`).
> The `framer-motion` package is a legacy alias that still works; this project pins `framer-motion@^12`.

## The one rule that matters most

**Never drive a continuous, user-controlled value (scroll progress, pointer position, physics) through React `useState`.** It re-renders the whole subtree every frame and collapses on mobile. Use **motion values** instead — they live outside React's render cycle and write straight to the DOM/Canvas.

```tsx
const { scrollYProgress } = useScroll();          // a MotionValue<number> 0..1
const y = useTransform(scrollYProgress, [0, 1], [0, -200]); // derived MotionValue
return <motion.div style={{ y }} />;              // no re-render on scroll
```

`window.addEventListener('scroll', ...)` is **banned** — unbatched, jank-prone. Use `useScroll`, `useMotionValueEvent`, `IntersectionObserver`, or CSS `animation-timeline: view()`.

## Scroll scrubbing

```tsx
const ref = useRef(null);
const { scrollYProgress } = useScroll({
  target: ref,
  offset: ['start start', 'end end'], // [whenTargetEdge hitsViewportEdge, ...]
});
```

`offset` pairs read `"<target> <viewport>"`. Common ones: `['start end','end start']` (element travels fully through the viewport), `['start start','end end']` (a tall pinned/sticky section scrubbed top-to-bottom).

To read the value imperatively in a rAF/Canvas loop without re-rendering, subscribe:

```tsx
useMotionValueEvent(scrollYProgress, 'change', (p) => { progressRef.current = p; });
// ...then read progressRef.current inside your own requestAnimationFrame loop
```

Smooth a jumpy scroll value with a spring before consuming it:

```tsx
const smooth = useSpring(scrollYProgress, { stiffness: 60, damping: 20, mass: 0.6 });
```

## Reveal on enter (lighter than any scroll library)

```tsx
<motion.section
  initial={reduce ? false : { opacity: 0, y: 24 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true, amount: 0.3 }}
  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }} // ease-out-expo, no bounce
/>
```

Stagger children by sharing variants in one client component tree:

```tsx
const parent = { show: { transition: { staggerChildren: 0.06 } } };
const child  = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } };
<motion.ul variants={parent} initial="hidden" whileInView="show" viewport={{ once: true }}>
  {items.map((it) => <motion.li key={it} variants={child}>{it}</motion.li>)}
</motion.ul>
```

## Springs & easing

- Prefer spring physics for interactive motion: `transition={{ type: 'spring', stiffness: 100, damping: 20 }}`.
- For timed eases use **ease-out exponential** curves (`[0.16, 1, 0.3, 1]`). No bounce, no elastic on UI.
- `layout` / `layoutId` for shared-element and list-reorder transitions — never wrap static content in `layout` "for safety" (it costs measurement work every commit).

## Reduced motion (non-negotiable)

```tsx
const reduce = useReducedMotion();
// gate entrance/parallax/physics: when `reduce`, render the final state statically.
```

Infinite loops, parallax, scroll-hijack, and pointer physics must collapse to static/instant under `prefers-reduced-motion: reduce`.

## Performance checklist

- Animate **only** `transform` and `opacity`. Never `top/left/width/height`.
- `will-change: transform` sparingly, only on elements that actually move.
- Isolate every motion component in a `'use client'` leaf; keep Server Components static.
- One animation system per subtree — do **not** mix GSAP/Three.js with Motion in the same tree; they fight for frames.
- For hundreds of moving points, skip per-element `motion.div` — drive a single `<canvas>` from a motion value in your own rAF loop (what this project's `CinematicScroll` does).
