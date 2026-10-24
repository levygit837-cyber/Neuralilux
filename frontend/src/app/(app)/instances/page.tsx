'use client'

import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { instanceService, type Instance, type InstanceStatus } from '@/services/instanceService'
import { useInstances } from '@/hooks/useInstances'
import { queryKeys } from '@/lib/queryKeys'
import { useInstanceStore, type SelectedInstance } from '@/stores/useInstanceStore'
import { ROUTES } from '@/lib/constants'

const STATUS_LABEL: Record<InstanceStatus, { label: string; color: string }> = {
  connected: { label: 'Conectada', color: 'text-status-success' },
  connecting: { label: 'Conectando', color: 'text-status-warning' },
  disconnected: { label: 'Desconectada', color: 'text-status-error' },
}

// Mesmo conjunto que a Evolution aceita no nome de uma Instance.
const NAME_PATTERN = /^[A-Za-z0-9_-]{3,60}$/

const messageOf = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback)

export default function InstancesPage() {
  const router = useRouter()
  const setSelectedInstance = useInstanceStore((state) => state.setSelectedInstance)
  const queryClient = useQueryClient()
  const query = useInstances()
  const instances = query.data ?? []
  const isLoading = query.isPending
  const [actionError, setActionError] = useState<string | null>(null)
  const error = actionError ?? (query.isError ? messageOf(query.error, 'Falha ao listar as instâncias') : null)
  const [newName, setNewName] = useState('')
  const [busyName, setBusyName] = useState<string | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.instances })
  const createMutation = useMutation({
    mutationFn: async (name: string): Promise<SelectedInstance> => {
      const { id } = await instanceService.create(name)
      return { id, name, status: 'disconnected' }
    },
    // Devolver a promise faz a mutation esperar a lista nova: ao abrir o QR, a Instance já está nela.
    onSettled: invalidate,
  })
  const deleteMutation = useMutation({
    mutationFn: (name: string) => instanceService.remove(name),
    onSettled: invalidate,
  })
  const isCreating = createMutation.isPending

  const open = (instance: SelectedInstance, route: string) => {
    setSelectedInstance({ id: instance.id, name: instance.name, status: instance.status })
    router.push(route)
  }

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault()
    const name = newName.trim()
    if (!NAME_PATTERN.test(name)) {
      setActionError('Use de 3 a 60 caracteres: letras, números, "-" ou "_".')
      return
    }

    setActionError(null)
    try {
      const created = await createMutation.mutateAsync(name)
      setNewName('')
      open(created, ROUTES.QR)
    } catch (e) {
      setActionError(messageOf(e, 'Falha ao criar a instância'))
    }
  }

  const handleDelete = async (instance: Instance) => {
    if (!window.confirm(`Apagar a instância "${instance.name}"? Isso desconecta o número e não pode ser desfeito.`)) return
    setBusyName(instance.name)
    setActionError(null)
    try {
      await deleteMutation.mutateAsync(instance.name)
      if (useInstanceStore.getState().selectedInstance?.id === instance.id) setSelectedInstance(null)
    } catch (e) {
      setActionError(messageOf(e, 'Falha ao apagar a instância'))
    } finally {
      setBusyName(null)
    }
  }

  return (
    <div className="space-y-6 p-4 sm:p-8">
      {error && (
        <div role="alert" className="rounded-lg border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-status-error">
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
            <p className="text-content-muted">Carregando...</p>
          ) : query.isError ? null : instances.length === 0 ? (
            <p className="text-content-muted">Você ainda não tem nenhuma instância. Crie a primeira acima.</p>
          ) : (
            <ul className="divide-y divide-brand-border">
              {instances.map((instance) => {
                const state = STATUS_LABEL[instance.status]
                return (
                  <li key={instance.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
                    <div>
                      <p className="font-semibold text-content-light">{instance.name}</p>
                      <p className="text-sm text-content-muted">
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
    </div>
  )
}
