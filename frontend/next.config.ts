import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // Keep Auth.js's own routes on the Next.js server (do NOT proxy them).
      {
        source: "/api/auth/:path*",
        destination: "/api/auth/:path*",
      },
      // Proxy all other /api/* calls to the FastAPI backend.
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8001/api/:path*",
      },
    ];
  },
};

export default nextConfig;
