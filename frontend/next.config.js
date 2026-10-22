/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
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
