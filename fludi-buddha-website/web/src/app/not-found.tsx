import Link from "next/link";
import AskButton from "@/components/site/AskButton";

export default function NotFound() {
  return (
    <main id="main" className="nf">
      <div className="wrap">
        <p className="nf-code" aria-hidden>404</p>
        <h1 className="t-h2">This page is not on the site.</h1>
        <p className="t-lead">The link may be old, or the address mistyped. FluidBuddha never sends visitors to a missing page, so we are sorry this one did.</p>
        <div className="ctas">
          <Link href="/" className="btn btn-primary btn-lg">Go to the home page</Link>
          <Link href="/pricing" className="btn btn-quiet btn-lg">See pricing</Link>
          <AskButton question="What can you do?">Ask Pragya instead</AskButton>
        </div>
      </div>
    </main>
  );
}
