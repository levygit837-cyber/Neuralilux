'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Zap, Eye, EyeOff, Mail, Lock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuthStore } from '@/stores/useAuthStore'
import { authService } from '@/services/authService'
import { ROUTES } from '@/lib/constants'

export default function LoginPage() {
  const router = useRouter()
  const login = useAuthStore((state) => state.login)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      // Login via API
      const { access_token } = await authService.login({ email, password })

      // Obter dados do usuário
      const userData = await authService.getCurrentUser(access_token)

      // Salvar no store
      login(
        {
          id: userData.id,
          name: userData.full_name || userData.email,
          email: userData.email,
        },
        access_token
      )

      router.push(ROUTES.DASHBOARD)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Email ou senha inválidos')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-dark">
      {/* Background gradient circles */}
      <div className="absolute left-[100px] top-[100px] h-[400px] w-[400px] rounded-full bg-gradient-radial from-primary/20 to-transparent blur-3xl" />
      <div className="absolute bottom-[100px] right-[100px] h-[300px] w-[300px] rounded-full bg-gradient-radial from-secondary-violet/20 to-transparent blur-3xl" />

      {/* Login card */}
      <div className="relative z-10 w-full max-w-[440px] rounded-[20px] border border-border-color bg-card p-12 shadow-2xl">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/30">
            <Zap className="h-8 w-8 text-text-light" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-text-light">
              Bem-vindo ao Neuralilux
            </h1>
            <p className="mt-2 text-sm text-text-gray">
              Faça login para continuar
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium text-text-light">
              Email ou Usuário
            </label>
            <Input
              id="email"
              type="email"
              placeholder="seu@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              icon={<Mail className="h-5 w-5" />}
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium text-text-light">
              Senha
            </label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                icon={<Lock className="h-5 w-5" />}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-gray"
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 rounded border-border-color bg-dark text-primary focus:ring-2 focus:ring-primary"
              />
              <span className="text-sm text-text-gray">Manter-se conectado</span>
            </label>
            <button
              type="button"
              className="text-sm font-medium text-primary hover:text-primary-light"
            >
              Esqueci a senha
            </button>
          </div>

          {error && (
            <div className="rounded-md bg-error/10 p-3 text-sm text-error">
              {error}
            </div>
          )}

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full"
            size="lg"
          >
            {isLoading ? 'Entrando...' : 'Entrar'}
          </Button>
        </form>
      </div>
    </div>
  )
}
