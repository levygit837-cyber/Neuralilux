import Link from 'next/link'
import { ROUTES } from '@/lib/constants'

export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-xl font-semibold text-text-light">Página não encontrada</h2>
      <Link href={ROUTES.HOME} className="text-primary hover:text-primary-light">
        Voltar ao início
      </Link>
    </div>
  )
}
