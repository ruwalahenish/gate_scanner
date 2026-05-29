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
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
      },
      {
        source: "/ws",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/ws`,
      },
    ];
  },
};

export default nextConfig;
