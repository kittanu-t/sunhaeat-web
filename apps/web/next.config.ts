import type { NextConfig } from "next";

// No cacheComponents: its prerendered shell cannot carry a per-request CSP nonce.
const nextConfig: NextConfig = { poweredByHeader: false, reactStrictMode: true };

export default nextConfig;
