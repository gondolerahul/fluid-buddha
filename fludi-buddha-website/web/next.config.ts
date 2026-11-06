import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // The app has its own lockfile; stop Next from picking up a stray one higher up.
  turbopack: { root: __dirname },
};

export default nextConfig;
