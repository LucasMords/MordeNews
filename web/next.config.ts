import type { NextConfig } from "next";

// Portal pessoal: não deve ser indexado nem aberto dentro de outro site.
const cabecalhos = [
  { key: "X-Robots-Tag", value: "noindex, nofollow" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
];

const config: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:caminho*", headers: cabecalhos }];
  },
};

export default config;
