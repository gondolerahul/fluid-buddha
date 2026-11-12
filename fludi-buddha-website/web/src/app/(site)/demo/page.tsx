import type { Metadata } from "next";
import Link from "next/link";
import DemoStage from "@/components/DemoStage";
import SandboxForm from "@/components/SandboxForm";

export const metadata: Metadata = {
  title: "Live demo",
  description: "Talk to a website that answers. Then hear your own website talk, from a few of its public pages.",
  alternates: { canonical: "/demo" },
};

const CONSOLE = process.env.NEXT_PUBLIC_CONSOLE_URL ?? "http://localhost:3001";

export default function DemoPage() {
  return (
    <>
      <section className="cp-hero">
        <div className="wrap dm-stage">
          <div className="cp-hero-copy" data-enter>
            <h1 className="t-display">This website runs on FluidBuddha. <span className="em">Talk to it.</span></h1>
            <p className="t-lead">Pick a question, or ask your own with the light in the corner, by voice or text. Each answer shows where it came from.</p>
          </div>
          <DemoStage />
        </div>
      </section>

      <section id="your-site" className="section tone-second">
        <div className="wrap dm-stage">
          <div className="sh" style={{ marginBottom: 0 }}>
            <h2 className="t-h2">Now hear <span className="em">your own website</span> talk.</h2>
            <p className="t-lead">In about a minute it reads a few of your public pages, learns what you sell and picks up your brand colours. Then it answers your customers&apos; questions in your website&apos;s own words, in English or Hindi.</p>
          </div>
          <SandboxForm />
        </div>
      </section>

      <section id="start" className="section cp-close tone-gold">
        <div className="wrap">
          <h2 className="t-h2">One line of code, <span className="em">on your site.</span></h2>
          <p className="t-lead">Create your account, paste the line, and your website starts answering this afternoon. The Free plan covers 100 conversations a month.</p>
          <div className="ctas">
            <a href={`${CONSOLE}/register`} className="btn btn-primary btn-lg">Create your free account</a>
            <Link href="/pricing" className="btn btn-quiet btn-lg">See pricing</Link>
          </div>
        </div>
      </section>
    </>
  );
}
