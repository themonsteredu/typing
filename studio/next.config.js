/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle for Docker (.next/standalone).
  output: "standalone",
  // The studio is one app inside a larger repo; trace files from the repo root.
  experimental: {
    outputFileTracingRoot: require("path").join(__dirname, ".."),
  },
};

module.exports = nextConfig;
