'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { instanceService, EvolutionInstance } from '@/services/instanceService'
import { useInstanceStore, SelectedInstance } from '@/stores/useInstanceStore'
import { ROUTES } from '@/lib/constants'
import { MessageCircle, Wifi, WifiOff, Loader2, RefreshCw, Smartphone } from 'lucide-react'

const STATUS_CONFIG = {
  open: {
    label: 'Conectado',
    color: 'text-success',
    bgColor: 'bg-success/10',
    borderColor: 'border-success/30',
    icon: Wifi,
  },
  close: {
    label: 'Desconectado',
    color: 'text-error',
    bgColor: 'bg-error/10',
    borderColor: 'border-error/30',
    icon: WifiOff,
  },
  connecting: {
    label: 'Conectando',
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    borderColor: 'border-warning/30',
    icon: Loader2,
  },
}

export default function HomePage() {
  const router = useRouter()
  const { setSelectedInstance } = useInstanceStore()
  const [instances, setInstances] = useState<EvolutionInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchInstances = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await instanceService.fetchInstances()
      setInstances(data)
    } catch (err) {
      console.error('Failed to fetch instances:', err)
      setError('Erro ao carregar instâncias. Verifique se a Evolution API está rodando.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchInstances()
  }, [])

  const handleSelectInstance = (instance: EvolutionInstance) => {
    const selected: SelectedInstance = {
      instanceName: instance.instance.instanceName,
      instanceId: instance.instance.instanceId,
      status: instance.instance.state || instance.socket?.state || 'close',
    }
    setSelectedInstance(selected)
    router.push(ROUTES.CHAT)
  }

  const handleConnect = (instance: EvolutionInstance) => {
    const selected: SelectedInstance = {
      instanceName: instance.instance.instanceName,
      instanceId: instance.instance.instanceId,
      status: instance.instance.state || instance.socket?.state || 'close',
    }
    setSelectedInstance(selected)
    router.push(ROUTES.QR)
  }

  return (
    <div className="flex min-h-screen bg-dark">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title="Instâncias WhatsApp" />
        <main className="flex-1 overflow-auto p-8">
          <div className="mx-auto max-w-6xl">
            {/* Header Section */}
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-text-light">Suas Instâncias</h2>
                <p className="mt-1 text-text-gray">
                  Selecione uma instância para gerenciar suas conversas
                </p>
              </div>
              <Button onClick={fetchInstances} variant="secondary" disabled={isLoading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                Atualizar
              </Button>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-6 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {error}
              </div>
            )}

            {/* Loading State */}
            {isLoading && (
              <div className="flex flex-col items-center justify-center py-20">
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                <p className="mt-4 text-text-gray">Carregando instâncias...</p>
              </div>
            )}

            {/* Empty State */}
            {!isLoading && !error && instances.length === 0 && (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border-color py-20">
                <Smartphone className="h-16 w-16 text-text-muted" />
                <h3 className="mt-4 text-lg font-semibold text-text-light">
                  Nenhuma instância encontrada
                </h3>
                <p className="mt-2 text-center text-text-gray">
                  Crie uma instância na Evolution API para começar
                </p>
              </div>
            )}

            {/* Instances Grid */}
            {!isLoading && instances.length > 0 && (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
                {instances.map((instance) => {
                  const state = instance.instance.state || instance.socket?.state || 'close'
                  const statusConfig = STATUS_CONFIG[state] || STATUS_CONFIG.close
                  const StatusIcon = statusConfig.icon

                  return (
                    <Card
                      key={instance.instance.instanceId}
                      className={`cursor-pointer transition-all hover:scale-[1.02] hover:shadow-lg ${statusConfig.borderColor} border-2`}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${statusConfig.bgColor}`}>
                              <MessageCircle className={`h-6 w-6 ${statusConfig.color}`} />
                            </div>
                            <div>
                              <CardTitle className="text-lg">{instance.instance.instanceName}</CardTitle>
                              <CardDescription className="text-xs">
                                ID: {instance.instance.instanceId.slice(0, 8)}...
                              </CardDescription>
                            </div>
                          </div>
                          <div className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 ${statusConfig.bgColor}`}>
                            <StatusIcon className={`h-4 w-4 ${statusConfig.color} ${state === 'connecting' ? 'animate-spin' : ''}`} />
                            <span className={`text-xs font-medium ${statusConfig.color}`}>
                              {statusConfig.label}
                            </span>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-0">
                        <div className="flex gap-2">
                          <Button
                            onClick={() => handleSelectInstance(instance)}
                            className="flex-1"
                            size="sm"
                          >
                            <MessageCircle className="mr-2 h-4 w-4" />
                            Abrir Chat
                          </Button>
                          <Button
                            onClick={() => handleConnect(instance)}
                            variant="secondary"
                            size="sm"
                          >
                            {state === 'open' ? 'QR Code' : 'Conectar'}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            )}

            {/* Current Instance Info */}
            {!isLoading && instances.length > 0 && (
              <div className="mt-8 rounded-lg border border-border-color bg-card p-4">
                <p className="text-sm text-text-gray">
                  <strong className="text-text-light">Dica:</strong> Clique em &quot;Abrir Chat&quot; para ver as conversas ou &quot;Conectar&quot; para escanear o QR Code.
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
