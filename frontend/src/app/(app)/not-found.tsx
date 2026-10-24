import Link from 'next/link'
import { POST_LOGIN_ROUTE } from '@/lib/constants'

export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-xl font-semibold text-content-light">Página não encontrada</h2>
      <Link href={POST_LOGIN_ROUTE} className="text-primary-light hover:text-primary-light">
        Voltar ao painel
      </Link>
    </div>
  )
}
