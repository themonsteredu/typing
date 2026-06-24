/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API routes spawn the Python engine; keep server-only deps out of the bundle.
  experimental: {
    serverComponentsExternalPackages: [],
  },
};

module.exports = nextConfig;
