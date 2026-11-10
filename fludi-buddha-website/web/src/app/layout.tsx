import type { Metadata } from "next";
import localFont from "next/font/local";
import { Space_Grotesk, Hanken_Grotesk, JetBrains_Mono, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import AskBar from "@/components/AskBar";
import RevealObserver from "@/components/RevealObserver";
import AgentLoader from "@/components/AgentLoader";

const roblox = localFont({
  variable: "--font-roblox",
  display: "swap",
  src: [
    { path: "./fonts/roblox-light.woff2", weight: "300" },
    { path: "./fonts/roblox-regular.woff2", weight: "400" },
    { path: "./fonts/roblox-bold.woff2", weight: "700" },
    { path: "./fonts/roblox-black.woff2", weight: "900" },
  ],
});
const space = Space_Grotesk({ subsets: ["latin"], weight: ["300", "400", "500"], variable: "--font-space", display: "swap" });
const hanken = Hanken_Grotesk({ subsets: ["latin"], weight: ["300", "400", "500", "600"], variable: "--font-hanken", display: "swap" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jetbrains", display: "swap" });
const deva = Noto_Sans_Devanagari({ subsets: ["devanagari"], weight: ["300", "400", "500"], variable: "--font-noto-deva", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL("https://fluidbuddha.com"),
  title: { default: "FluidBuddha — Your website, answering every visitor", template: "%s · FluidBuddha" },
  description:
    "FluidBuddha turns your website into a voice-first agent. It listens, speaks, shows and books, using only what your website says.",
  openGraph: { siteName: "FluidBuddha", type: "website" },
  alternates: { languages: { "en-IN": "/", "hi-IN": "/hi" } },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="paper" className={`${roblox.variable} ${space.variable} ${hanken.variable} ${jetbrains.variable} ${deva.variable}`}>
      <body>
        <a href="#main" className="sr-only">Skip to content</a>
        <Nav />
        <main id="main">{children}</main>
        <Footer />
        <AskBar />
        <RevealObserver />
        <AgentLoader />
      </body>
    </html>
  );
}
