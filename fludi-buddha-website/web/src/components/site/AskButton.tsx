"use client";

/** A button that asks the site's own agent a question (Ask Pragya opens and answers). */
export default function AskButton({ question, className = "cp-try", children }: { question: string; className?: string; children?: React.ReactNode }) {
  return (
    <button type="button" className={className} onClick={() => window.dispatchEvent(new CustomEvent("fb:ask", { detail: question }))}>
      {children ?? <>Ask it: &ldquo;{question}&rdquo;</>}
    </button>
  );
}
