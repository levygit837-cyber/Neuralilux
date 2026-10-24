import { LoginForm } from '@/components/auth/LoginForm'
import { safeCallbackUrl } from '@/lib/safeCallbackUrl'

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string | string[] }>
}) {
  const { callbackUrl } = await searchParams
  return <LoginForm callbackUrl={safeCallbackUrl(callbackUrl)} />
}
