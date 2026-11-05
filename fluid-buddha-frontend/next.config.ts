import type { NextConfig } from "next";

// Security headers for every console page (M2-11). The console talks to the
// backend (API + the live inbox's WebSocket) and Razorpay's checkout (billing);
// nothing else. Next.js needs inline scripts for hydration ('unsafe-inline';
// 'unsafe-eval' only in development for fast refresh).
const isDev = process.env.NODE_ENV === "development";
const api = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080").replace(/\/$/, "");
const widget = (process.env.NEXT_PUBLIC_WIDGET_BACKEND || api.replace(/^http/, "ws")).replace(/\/$/, "");
const origin = (u: string) => {
  try {
    return new URL(u).origin;
  } catch {
    return "";
  }
};
const apiOrigin = origin(api);
const wsOrigin = origin(widget.replace(/^ws/, "http")).replace(/^http/, "ws");
const razorpay = "https://*.razorpay.com";

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} https://checkout.razorpay.com`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data: https:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin} ${wsOrigin} ${razorpay}`,
  `frame-src 'self' ${razorpay}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // The live inbox's voice handoff needs the microphone; nothing needs the rest.
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=(), payment=(self)" },
  ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The self-hosted image (deploy/selfhost, M3-5) runs the standalone server.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" as const } : {}),
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
