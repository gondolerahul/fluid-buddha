import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import DemoStage from "@/components/DemoStage";
import SandboxForm from "@/components/SandboxForm";
import Theme from "@/components/Theme";
import styles from "./demo.module.css";

export const metadata: Metadata = {
  title: "Live demo",
  description: "Talk to a website that answers. Then hear your own website talk, from a few of its public pages.",
};

const CONSOLE = process.env.NEXT_PUBLIC_CONSOLE_URL ?? "http://localhost:3001";

export default function DemoPage() {
  return (
    <>
      <Theme theme="ink" />
      <section className={styles.stage}>
        <div className={styles.bg}><Image src="/film/posters/K9.webp" alt="" fill priority sizes="100vw" /></div>
        <div className={styles.veil} />
        <div className={`wrap ${styles.stageGrid}`}>
          <div className="stack-5">
            <div className="eyebrow">Live demo</div>
            <h1 className="h1">Don&apos;t read about it. <span className="gold">Talk to it.</span></h1>
            <p className="lead">This website runs on FluidBuddha. Pick a question, or ask your own in the bar below, by voice or text.</p>
          </div>
          <DemoStage />
        </div>
      </section>

      <section id="your-site" className={`section ${styles.yours}`}>
        <div className={`wrap ${styles.yoursGrid}`}>
          <div className="stack-5 reveal">
            <div className="eyebrow">Now try it on your own website</div>
            <h2 className="h1">Enter your website. <span className="gold">Hear it talk.</span></h2>
            <p className="lead">In about a minute, hear your own website answer your customers&apos; questions, using only what&apos;s already on it, in English or Hindi, with links to your own pages.</p>
            <ol className={styles.how}>
              <li><b>Read</b> a few of your public pages</li>
              <li><b>Learn</b> what you sell, and who your customers are</li>
              <li><b>Pick up</b> your brand colours</li>
              <li><b>Answer</b>, in your own website&apos;s words</li>
            </ol>
          </div>
          <div className="reveal"><SandboxForm /></div>
        </div>
      </section>

      <section id="start" className={`section ${styles.start}`}>
        <div className="wrap" style={{ textAlign: "center" }}>
          <div className="stack-5 reveal" style={{ maxWidth: 760, marginInline: "auto" }}>
            <div className="eyebrow">Free plan · 100 conversations</div>
            <h2 className="h1">One drop, <span className="gold">on your site.</span></h2>
            <p className="lead" style={{ marginInline: "auto" }}>Create your account, paste one line of code, and your website starts answering this afternoon.</p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
              <a href={`${CONSOLE}/register`} className="btn btn-metal btn-lg">Create your free account</a>
              <Link href="/pricing" className="btn btn-ghost btn-lg">See pricing</Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
