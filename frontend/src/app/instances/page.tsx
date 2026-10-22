'use client'

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { instanceService, type Instance, type InstanceStatus } from '@/services/instanceService'
import { useInstanceStore } from '@/stores/useInstanceStore'
import { ROUTES } from '@/lib/constants'

const STATUS_LABEL: Record<InstanceStatus, { label: string; color: string }> = {
  connected: { label: 'Conectada', color: 'text-success' },
  connecting: { label: 'Conectando', color: 'text-warning' },
  disconnected: { label: 'Desconectada', color: 'text-error' },
}

// Mesmo conjunto que a Evolution aceita no nome de uma Instance.
const NAME_PATTERN = /^[A-Za-z0-9_-]{3,60}$/

const messageOf = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback)

export default function InstancesPage() {
  const router = useRouter()
  const setSelectedInstance = useInstanceStore((state) => state.setSelectedInstance)
  const [instances, setInstances] = useState<Instance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [busyName, setBusyName] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setInstances(await instanceService.list())
      setError(null)
    } catch (e) {
      setError(messageOf(e, 'Falha ao listar as instâncias'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const loadOnMount = async () => {
      await load()
    }
    void loadOnMount()
  }, [load])

  const open = (instance: Instance, route: string) => {
    setSelectedInstance({ id: instance.id, name: instance.name, status: instance.status })
    router.push(route)
  }

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault()
    const name = newName.trim()
    if (!NAME_PATTERN.test(name)) {
      setError('Use de 3 a 60 caracteres: letras, números, "-" ou "_".')
      return
    }

    setIsCreating(true)
    setError(null)
    try {
      await instanceService.create(name)
      const created = (await instanceService.list()).find((item) => item.name === name)
      setNewName('')
      if (created) open(created, ROUTES.QR)
      else await load()
    } catch (e) {
      setError(messageOf(e, 'Falha ao criar a instância'))
    } finally {
      setIsCreating(false)
    }
  }

  const handleDelete = async (instance: Instance) => {
    if (!window.confirm(`Apagar a instância "${instance.name}"? Isso desconecta o número e não pode ser desfeito.`)) return
    setBusyName(instance.name)
    setError(null)
    try {
      await instanceService.remove(instance.name)
      if (useInstanceStore.getState().selectedInstance?.id === instance.id) setSelectedInstance(null)
      await load()
    } catch (e) {
      setError(messageOf(e, 'Falha ao apagar a instância'))
    } finally {
      setBusyName(null)
    }
  }

  return (
    <div className="flex min-h-screen bg-dark">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title="Instâncias" showOnlineBadge={false} />
        <main className="flex-1 space-y-6 p-8">
          {error && (
            <div role="alert" className="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
              {error}
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Nova instância</CardTitle>
              <CardDescription>Cada instância é um número de WhatsApp. Depois de criar, leia o QR code.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="flex flex-col gap-3 sm:flex-row">
                <Input
                  aria-label="Nome da instância"
                  placeholder="ex.: loja-centro"
                  value={newName}
                  onChange={(event) => setNewName(event.target.value)}
                  disabled={isCreating}
                />
                <Button type="submit" disabled={isCreating || newName.trim() === ''}>
                  {isCreating ? 'Criando...' : 'Criar instância'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Suas instâncias</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <p className="text-text-muted">Carregando...</p>
              ) : instances.length === 0 ? (
                <p className="text-text-muted">Você ainda não tem nenhuma instância. Crie a primeira acima.</p>
              ) : (
                <ul className="divide-y divide-border-color">
                  {instances.map((instance) => {
                    const state = STATUS_LABEL[instance.status]
                    return (
                      <li key={instance.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
                        <div>
                          <p className="font-semibold text-text-light">{instance.name}</p>
                          <p className="text-sm text-text-muted">
                            <span className={state.color}>{state.label}</span>
                            {instance.profileName && ` · ${instance.profileName}`}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => open(instance, ROUTES.CHAT)}>
                            Abrir chat
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => open(instance, ROUTES.QR)}>
                            Conexão
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            aria-label={`Apagar a instância ${instance.name}`}
                            disabled={busyName === instance.name}
                            onClick={() => void handleDelete(instance)}
                          >
                            Apagar
                          </Button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  )
}
