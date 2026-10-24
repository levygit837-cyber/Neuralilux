/** @type {import('next').NextConfig} */
const nextConfig = {
  // Servidor mínimo para a imagem Docker (.next/standalone); veja frontend/Dockerfile.
  output: 'standalone',
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  // Cabeçalhos que não dependem da requisição. A CSP (com nonce por requisição e frame-ancestors) é do src/proxy.ts.
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'DENY' },
        ],
      },
    ]
  },
  images: {
    remotePatterns: [
      { protocol: 'http', hostname: 'localhost' },
      // Fotos de perfil dos Contacts servidas pelo WhatsApp (Evolution API devolve profilePicUrl).
      { protocol: 'https', hostname: 'pps.whatsapp.net' },
      { protocol: 'https', hostname: '**.whatsapp.net' },
    ],
  },
}

module.exports = nextConfig
