import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Space_Grotesk, Hanken_Grotesk, JetBrains_Mono, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";
import AskPragya from "@/components/site/AskPragya";
import WorldSwitch from "@/components/world/WorldSwitch";
import AgentLoader from "@/components/AgentLoader";
import InlineScript from "@/components/site/InlineScript";
import { WORLD_BOOT } from "@/lib/world";

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
// The design system's faces (buddha-cognitive-lab-design-system/project/colors_and_type.css):
// Roblox for the logotype and hero words, Space Grotesk for headings, Hanken Grotesk for reading,
// JetBrains Mono for data. Noto Sans Devanagari is added for the Hindi showcase.
const space = Space_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-space", display: "swap" });
const hanken = Hanken_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-hanken", display: "swap" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jetbrains", display: "swap", preload: false });
const deva = Noto_Sans_Devanagari({ subsets: ["devanagari"], weight: ["400", "500", "600"], variable: "--font-noto-deva", display: "swap", preload: false });

export const metadata: Metadata = {
  metadataBase: new URL("https://fluidbuddha.com"),
  title: { default: "FluidBuddha: your website, answering every visitor", template: "%s · FluidBuddha" },
  description:
    "FluidBuddha lets your website answer visitors by voice or text, using only your own content. It shows prices and charts, takes people to the right page and books the meeting.",
  openGraph: { siteName: "FluidBuddha", type: "website", images: ["/film/stills/painted-page.jpg"] },
};

export const viewport: Viewport = { themeColor: "#0a0908", colorScheme: "dark light" };

/**
 * One chrome for the whole site: the header, the footer, the Ask Pragya light and the morph between
 * worlds are rendered here once, so they persist across navigation. The world (and so every colour,
 * radius and button) is set on <html data-world> by an inline script before the first paint.
 */
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-world="default" suppressHydrationWarning
          className={`${roblox.variable} ${space.variable} ${hanken.variable} ${jetbrains.variable} ${deva.variable}`}>
      <head>
        <InlineScript html={WORLD_BOOT} />
      </head>
      <body>
        <a href="#main" className="skip">Skip to content</a>
        <SiteHeader />
        {children}
        <SiteFooter />
        <AskPragya />
        <WorldSwitch />
        <AgentLoader />
      </body>
    </html>
  );
}
