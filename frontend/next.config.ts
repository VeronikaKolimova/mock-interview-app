import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    missingSuspenseWithCSRBailout: false,
  },
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },

};

export default nextConfig;
