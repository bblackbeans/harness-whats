import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      { source: "/tenants/new", destination: "/clientes/novo", permanent: false },
      { source: "/tenants/:id", destination: "/clientes/:id", permanent: false },
      { source: "/settings/plans", destination: "/settings/llm", permanent: false },
      { source: "/portal/model", destination: "/portal", permanent: false },
      { source: "/settings/model-requests", destination: "/settings/llm", permanent: false },
    ];
  },
};

export default nextConfig;
