"use client";

/**
 * A script that runs while the HTML is parsed, before the first paint (Next.js guide: "Preventing
 * flash before hydration"). On the client it renders as text/plain, so React never tries to run it
 * again during client rendering (for example when the not-found page renders).
 */
export default function InlineScript({ html }: { html: string }) {
  return (
    <script type={typeof window === "undefined" ? "text/javascript" : "text/plain"} suppressHydrationWarning dangerouslySetInnerHTML={{ __html: html }} />
  );
}
