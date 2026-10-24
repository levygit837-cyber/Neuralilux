import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

// A CSP leva um nonce novo por requisição (proxy.ts), então nenhuma página pode ser gerada em build.
export const dynamic = 'force-dynamic'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Neuralilux - Automação WhatsApp com IA',
  description: 'Sistema de automação de conversas no WhatsApp com agentes de IA',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <body className={inter.className}>{children}</body>
    </html>
  )
}
