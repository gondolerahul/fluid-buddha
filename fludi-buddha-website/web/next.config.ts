import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // The app has its own lockfile; stop Next from picking up a stray one higher up.
  turbopack: { root: __dirname },
  // Pages folded into a world or into the runtime Hindi switch (docs/marketing-docs/website/audit-2026-11-11.md §2.3).
  async redirects() {
    return [
      { source: "/industries/saas", destination: "/for/saas", permanent: true },
      { source: "/industries/education", destination: "/for/education", permanent: true },
      { source: "/enterprise", destination: "/for/enterprise", permanent: true },
      { source: "/customers", destination: "/about", permanent: true },
      { source: "/hi", destination: "/?lang=hi", permanent: true },
      { source: "/hi/pricing", destination: "/pricing?lang=hi", permanent: true },
      { source: "/hi/demo", destination: "/demo", permanent: true },
    ];
  },
};

export default nextConfig;
