import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use standalone output for Docker deployment
  output: "standalone",
  // Allow images from yfinance / NSE sources
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.nseindia.com" },
      { protocol: "https", hostname: "**.bseindia.com" },
    ],
  },
  // Rewrites so /api/* goes to FastAPI during development
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
      {
        source: "/ws",
        destination: `${apiUrl}/ws`,
      },
    ];
  },
};

export default nextConfig;
