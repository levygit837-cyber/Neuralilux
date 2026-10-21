import Image from 'next/image'

// Subdomínios de whatsapp.net (ex.: pps.whatsapp.net) estão em images.remotePatterns, em next.config.js.
const WHATSAPP_AVATAR_HOST = /\.whatsapp\.net$/

function isWhatsAppAvatar(src: string): boolean {
  try {
    const { protocol, hostname } = new URL(src)
    return protocol === 'https:' && WHATSAPP_AVATAR_HOST.test(hostname)
  } catch {
    return false
  }
}

interface AvatarImageProps {
  src: string
  /** Texto alternativo. Use '' só quando a imagem for decorativa. */
  alt: string
  sizes: string
  className?: string
  onError?: () => void
}

/**
 * Foto de perfil dentro de um contêiner `relative` com tamanho definido.
 * Hosts do WhatsApp passam pelo otimizador do Next; qualquer outro host (ou URL
 * relativa) é servido como veio, porque o `next/image` lança erro em hosts
 * fora de `remotePatterns`.
 */
export function AvatarImage({ src, alt, sizes, className, onError }: AvatarImageProps) {
  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes}
      unoptimized={!isWhatsAppAvatar(src)}
      aria-hidden={alt === '' ? true : undefined}
      className={className}
      onError={onError}
    />
  )
}
