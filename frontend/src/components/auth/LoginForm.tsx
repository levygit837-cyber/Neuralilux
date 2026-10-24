'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Zap, Eye, EyeOff, Mail, Lock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuthStore } from '@/stores/useAuthStore'
import { authService } from '@/services/authService'

interface LoginFormProps {
  callbackUrl: string
}

export function LoginForm({ callbackUrl }: LoginFormProps) {
  const router = useRouter()
  const login = useAuthStore((state) => state.login)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      // O login grava o cookie de sessão; o usuário vem de /auth/me com esse cookie.
      await authService.login({ email, password })
      const userData = await authService.getCurrentUser()

      login({
        id: userData.id,
        name: userData.full_name || userData.email,
        email: userData.email,
      })

      router.push(callbackUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Email ou senha inválidos')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-brand-base">
      {/* Background gradient circles */}
      <div className="absolute left-[100px] top-[100px] h-[400px] w-[400px] rounded-full bg-gradient-radial from-primary/20 to-transparent blur-3xl" />
      <div className="absolute bottom-[100px] right-[100px] h-[300px] w-[300px] rounded-full bg-gradient-radial from-secondary/20 to-transparent blur-3xl" />

      {/* Login card */}
      <div className="relative z-10 w-full max-w-[440px] rounded-[20px] border border-brand-border bg-brand-card p-12 shadow-2xl">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/30">
            <Zap className="h-8 w-8 text-content-light" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-content-light">
              Bem-vindo ao Neuralilux
            </h1>
            <p className="mt-2 text-sm text-content-gray">
              Faça login para continuar
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium text-content-light">
              Email ou Usuário
            </label>
            <Input
              id="email"
              type="email"
              placeholder="seu@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              icon={<Mail className="h-5 w-5" aria-hidden="true" />}
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium text-content-light">
              Senha
            </label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                icon={<Lock className="h-5 w-5" aria-hidden="true" />}
                required
              />
              <button
                type="button"
                aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                aria-pressed={showPassword}
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-content-muted hover:text-content-gray focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <Eye className="h-5 w-5" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              className="text-sm font-medium text-primary-light hover:text-primary-light"
            >
              Esqueci a senha
            </button>
          </div>

          {error && (
            <div className="rounded-md bg-status-error/10 p-3 text-sm text-status-error">
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
