'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Smartphone, Wifi, WifiOff, RefreshCw, QrCode, Trash2 } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { ROUTES } from '@/lib/constants'

interface Instance {
  id: string
  name: string
  status: 'connected' | 'disconnected' | 'connecting'
  phoneNumber?: string
  lastSeen?: string
}

const mockInstances: Instance[] = [
  {
    id: '1',
    name: 'Atendimento Principal',
    status: 'connected',
    phoneNumber: '+55 11 99999-9999',
    lastSeen: 'Agora',
  },
  {
    id: '2',
    name: 'Vendas',
    status: 'disconnected',
    phoneNumber: '+55 11 88888-8888',
    lastSeen: '2 horas atrás',
  },
  {
    id: '3',
    name: 'Suporte',
    status: 'connecting',
    phoneNumber: '+55 11 77777-7777',
    lastSeen: '5 minutos atrás',
  },
]

const STATUS_CONFIG = {
  connected: {
    label: 'Conectado',
    color: 'text-success',
    bgColor: 'bg-success/10',
    icon: Wifi,
    badgeVariant: 'success' as const,
  },
  disconnected: {
    label: 'Desconectado',
    color: 'text-error',
    bgColor: 'bg-error/10',
    icon: WifiOff,
    badgeVariant: 'error' as const,
  },
  connecting: {
    label: 'Conectando',
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    icon: RefreshCw,
    badgeVariant: 'warning' as const,
  },
}

export default function InstancesPage() {
  const router = useRouter()
  const [instances, setInstances] = useState<Instance[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadInstances = async () => {
      setIsLoading(true)
      await new Promise((resolve) => setTimeout(resolve, 1000))
      setInstances(mockInstances)
      setIsLoading(false)
    }
    loadInstances()
  }, [])

  const handleCreateInstance = () => {
    router.push(ROUTES.QR)
  }

  const handleConnect = (instanceId: string) => {
    router.push(`${ROUTES.QR}?instance=${instanceId}`)
  }

  const handleDisconnect = (instanceId: string) => {
    console.log('Disconnect instance:', instanceId)
  }

  const handleDelete = (instanceId: string) => {
    console.log('Delete instance:', instanceId)
  }

  return (
    <div className="flex min-h-screen flex-col bg-dark">
      <Header />
      <main className="flex-1 p-8">
        <div className="mx-auto max-w-7xl space-y-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-text-light">Instâncias WhatsApp</h1>
              <p className="mt-1 text-sm text-text-muted">
                Gerencie suas conexões do WhatsApp
              </p>
            </div>
            <Button onClick={handleCreateInstance} className="gap-2">
              <Plus className="h-4 w-4" />
              Nova Instância
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-success/10">
                  <Wifi className="h-6 w-6 text-success" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-text-light">
                    {instances.filter((i) => i.status === 'connected').length}
                  </p>
                  <p className="text-sm text-text-muted">Conectadas</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-error/10">
                  <WifiOff className="h-6 w-6 text-error" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-text-light">
                    {instances.filter((i) => i.status === 'disconnected').length}
                  </p>
                  <p className="text-sm text-text-muted">Desconectadas</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                  <Smartphone className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-text-light">{instances.length}</p>
                  <p className="text-sm text-text-muted">Total</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
