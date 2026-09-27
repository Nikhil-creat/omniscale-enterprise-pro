// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // "standalone" output is only needed for the self-hosted Docker image
  // (see ../Dockerfile). Vercel's own build pipeline handles output itself —
  // forcing standalone there is harmless but pointless, so it's opt-in via
  // an env var the Dockerfile sets and Vercel never will.
  ...(process.env.DOCKER_BUILD === "1" ? { output: "standalone" } : {}),
};

module.exports = nextConfig;
