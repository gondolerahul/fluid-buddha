# FluidBuddha on Framer

Two ways; both take a minute.

## A. Code component (recommended)

1. In Framer, open **Assets → Code → + → New component**, name it `FluidBuddha`,
   and replace its contents with [`FluidBuddha.tsx`](FluidBuddha.tsx).
2. Drag **FluidBuddha** onto your home page (or a component every page uses,
   such as the footer). Its size doesn't matter; it's only visible on the canvas.
3. In the properties panel, paste the **install code** from the FluidBuddha
   console (your website → **Install** → **Framer**). Optionally pick the position
   and language.
4. Publish. The agent appears in the corner of the live site.

On the canvas you see a small placeholder that says whether the code is valid;
the agent itself only loads on the published site and in Preview.

## B. Custom code

1. **Site settings → General → Custom code → End of `<body>` tag**.
2. Paste the snippet from the console (your website → **Install** → **Framer**):

   ```html
   <script src="https://<your-server>/widget/loader.js" data-key="fbk_…" async></script>
   ```

3. Publish.

Custom code needs a paid Framer site plan; the code component works on any plan.

## Notes

- The agent's colour, greeting, design and knowledge come from the FluidBuddha
  console; you don't need to republish when you change them.
- In the console, set the website's domain to your Framer domain (and your custom
  domain, if any) — the widget key only answers on that domain.
