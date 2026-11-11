import type { Metadata } from "next";
import Link from "next/link";
import FilmPlayer from "@/components/FilmPlayer";

export const metadata: Metadata = {
  title: { absolute: "FluidBuddha — आपकी वेबसाइट, हर विज़िटर को जवाब देती है" },
  description: "FluidBuddha आपकी वेबसाइट को बोलने वाला एजेंट बनाता है। यह सुनती है, बोलती है, दिखाती है और बुक करती है, सिर्फ़ आपकी वेबसाइट से।",
  alternates: { canonical: "/hi", languages: { "en-IN": "/" } },
};

export default function HindiHome() {
  return (
    <div lang="hi" className="deva">
      <FilmPlayer locale="hi" />
      <section className="section">
        <div className="wrap stack-5 reveal" style={{ textAlign: "center", maxWidth: 820 }}>
          <div className="eyebrow">हिंदी और अंग्रेज़ी</div>
          <h2 className="h2">आपके ग्राहक हिंग्लिश में पूछते हैं। <span className="gold">आपकी वेबसाइट हिंदी में जवाब देती है।</span></h2>
          <p className="lead" style={{ marginInline: "auto" }}>कोई अनुवाद प्रोजेक्ट नहीं। यह आपकी अंग्रेज़ी वेबसाइट से हिंदी में जवाब देती है, और ग्राहक के “हाँ” कहने पर बिक्री पूरी करती है।</p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/hi/demo" className="btn btn-metal btn-lg">लाइव डेमो</Link>
            <Link href="/hi/pricing" className="btn btn-ghost btn-lg">कीमतें देखें</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
