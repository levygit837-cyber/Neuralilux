import { MobileNav } from '@/components/layout/MobileNav'
import { QueryProvider } from '@/components/providers/QueryProvider'
import { RealtimeProvider } from '@/components/providers/RealtimeProvider'
import { RouteHeader } from '@/components/layout/RouteHeader'
import { SessionRestorer } from '@/components/providers/SessionRestorer'
import { Sidebar } from '@/components/layout/Sidebar'
import { AUTH_COOKIE_NAME, ROUTES } from '@/lib/constants'
import { checkSession } from '@/lib/session'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // O proxy já barra quem não tem sessão. Mas ele deixa de fora os arquivos do Next (`/favicon.ico`,
  // `/_next/static/...`) e, quando o arquivo não existe, a URL cai na rota coringa desta área e renderizaria o
  // shell. Esta checagem garante que nenhum caminho o renderize sem sessão válida.
  const cookie = (await cookies()).get(AUTH_COOKIE_NAME)?.value
  if ((await checkSession(cookie)) !== 'valid') redirect(ROUTES.LOGIN)
  return (
    <QueryProvider>
      <SessionRestorer />
      <RealtimeProvider>
        <div className="flex h-dvh overflow-hidden bg-brand-base">
          <Sidebar />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <MobileNav />
            <RouteHeader />
            <main className="flex min-h-0 flex-1 flex-col overflow-auto">{children}</main>
          </div>
        </div>
      </RealtimeProvider>
    </QueryProvider>
  )
}
