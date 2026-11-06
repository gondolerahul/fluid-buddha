import type { Metadata } from "next";
import Image from "next/image";
import DemoStage from "@/components/DemoStage";
import SandboxForm from "@/components/SandboxForm";
import Theme from "@/components/Theme";
import styles from "../../demo/demo.module.css";

export const metadata: Metadata = {
  title: { absolute: "लाइव डेमो · FluidBuddha" },
  description: "एक ऐसी वेबसाइट से बात कीजिए जो जवाब देती है। फिर अपनी वेबसाइट को बोलते हुए सुनिए।",
  alternates: { canonical: "/hi/demo", languages: { "en-IN": "/demo" } },
};

const CONSOLE = process.env.NEXT_PUBLIC_CONSOLE_URL ?? "http://localhost:3001";

export default function HindiDemo() {
  return (
    <div lang="hi" className="deva">
      <Theme theme="ink" />
      <section className={styles.stage}>
        <div className={styles.bg}><Image src="/film/posters/K9.webp" alt="" fill priority sizes="100vw" /></div>
        <div className={styles.veil} />
        <div className={`wrap ${styles.stageGrid}`}>
          <div className="stack-5">
            <div className="eyebrow">लाइव डेमो</div>
            <h1 className="h1">इसके बारे में पढ़िए नहीं। <span className="gold">इससे बात कीजिए।</span></h1>
            <p className="lead">यह वेबसाइट FluidBuddha पर चलती है। कोई सवाल चुनिए, या नीचे बार में बोलकर या लिखकर पूछिए।</p>
          </div>
          <DemoStage hindi />
        </div>
      </section>

      <section id="your-site" className={`section ${styles.yours}`}>
        <div className={`wrap ${styles.yoursGrid}`}>
          <div className="stack-5 reveal">
            <div className="eyebrow">अब अपनी वेबसाइट पर आज़माइए</div>
            <h2 className="h1">अपनी वेबसाइट डालिए। <span className="gold">उसे बोलते हुए सुनिए।</span></h2>
            <p className="lead">लगभग एक मिनट में सुनिए कि आपकी वेबसाइट आपके ग्राहकों के सवालों का जवाब कैसे देती है, सिर्फ़ उसी से जो उस पर पहले से लिखा है।</p>
          </div>
          <div className="reveal" lang="en"><SandboxForm /></div>
        </div>
      </section>

      <section id="start" className="section">
        <div className="wrap stack-5 reveal" style={{ textAlign: "center", maxWidth: 760 }}>
          <div className="eyebrow">फ़्री प्लान · 100 बातचीत</div>
          <h2 className="h1">एक बूंद, <span className="gold">आपकी साइट पर।</span></h2>
          <p className="lead" style={{ marginInline: "auto" }}>अकाउंट बनाइए, कोड की एक लाइन जोड़िए, और आपकी वेबसाइट आज दोपहर से जवाब देने लगेगी।</p>
          <div><a href={`${CONSOLE}/register`} className="btn btn-metal btn-lg">मुफ़्त अकाउंट बनाएँ</a></div>
        </div>
      </section>
    </div>
  );
}
