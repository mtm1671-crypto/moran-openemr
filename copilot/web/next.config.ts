import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: {
    ignoreDuringBuilds: true
  },
  output: "standalone",
  outputFileTracingRoot: process.cwd()
};

export default nextConfig;
