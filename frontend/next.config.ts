import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'pub-87c1d9b1e1834f4bbe644091f4abb511.r2.dev',
        pathname: '/**',
      },
    ],
  },
  // Ignore ESLint errors during build for faster deployment
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Ignore TypeScript errors during build
  typescript: {
    ignoreBuildErrors: true,
  },
  // Transpile lucide-react to avoid barrel optimization issues
  transpilePackages: ['lucide-react', '@webcontainer/api'],
  // Headers are now handled by middleware.ts for better control
  // BoxLite pages don't get COEP (allows iframe embedding)
  // Other pages get COEP for WebContainer support
};

export default nextConfig;
