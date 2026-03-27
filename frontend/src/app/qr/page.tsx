'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import QRCode from 'react-qr-code'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { useInstanceStore } from '@/stores/useInstanceStore'
import { instanceService } from '@/services/instanceService'
import { ROUTES } from '@/lib/constants'
import { ArrowLeft, Loader2 } from 'lucide-react'

type InstanceStatus = 'disconnected' | 'connecting' | 'connected'

const STATUS_CONFIG: Record<
  InstanceStatus,
  { label: string; color: string; bgColor: string }
> = {
  disconnected: {
    label: 'Desconectado',
    color: 'text-error',
    bgColor: 'bg-error/10',
  },
  connecting: {
    label: 'Conectando...',
    color: 'text-warning',
    bgColor: 'bg-warning/10',
  },
  connected: {
    label: 'Conectado',
    color: 'text-success',
    bgColor: 'bg-success/10',
  },
}

export default function QrPage() {
  const router = useRouter()
  const { selectedInstance, clearInstance } = useInstanceStore()

  const [status, setStatus] = useState<InstanceStatus>('disconnected')
  const [qrCode, setQrCode] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

  const instanceName = selectedInstance?.instanceName

  const stopPolling = useCallback(() => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      setPollingInterval(null)
    }
  }, [pollingInterval])

  const checkStatus = useCallback(async () => {
    if (!instanceName) return
    try {
      const response = await instanceService.getConnectionState(instanceName)
      const state = response.instance.state
      if (state === 'open') {
        setStatus('connected')
        setQrCode(null)
        stopPolling()
      } else if (state === 'connecting') {
        setStatus('connecting')
      } else {
        setStatus('disconnected')
      }
    } catch {
      // Silent fail for polling
    }
  }, [instanceName, stopPolling])

  const startPolling = useCallback(() => {
    stopPolling()
    const interval = setInterval(checkStatus, 3000)
    setPollingInterval(interval)
  }, [checkStatus, stopPolling])

  useEffect(() => {
    if (instanceName) {
      checkStatus()
    }
    return () => stopPolling()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instanceName])

  useEffect(() => {
    if (status === 'connected') {
      stopPolling()
    }
  }, [status, stopPolling])

  const handleConnect = async () => {
    if (!instanceName) {
      setError('Nenhuma instância selecionada')
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const response = await instanceService.connectInstance(instanceName)
      setStatus('connecting')

      if (response.base64) {
        setQrCode(response.base64)
      }

      startPolling()

      // Refresh QR code periodically
      const qrInterval = setInterval(async () => {
        try {
          const qrResponse = await instanceService.connectInstance(instanceName)
          if (qrResponse.base64) {
            setQrCode(qrResponse.base64)
          }
        } catch {
          // QR might not be ready yet
        }
      }, 3000)

      setTimeout(() => clearInterval(qrInterval), 120000)
    } catch {
      setError('Erro ao conectar. Verifique se a Evolution API está rodando.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDisconnect = async () => {
    if (!instanceName) return
    setIsLoading(true)
    setError(null)
    try {
      await instanceService.logoutInstance(instanceName)
      setStatus('disconnected')
      setQrCode(null)
      stopPolling()
    } catch {
      setError('Erro ao desconectar.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleBack = () => {
    clearInstance()
    router.push(ROUTES.HOME)
  }

  const statusConfig = STATUS_CONFIG[status]

  // No instance selected
  if (!selectedInstance) {
    return (
      <div className="flex min-h-screen bg-dark">
        <Sidebar />
        <div className="flex flex-1 flex-col">
          <Header title="QR Code" />
          <main className="flex flex-1 items-center justify-center p-8">
            <Card className="w-full max-w-md">
              <CardContent className="flex flex-col items-center py-12">
                <p className="text-text-gray">Nenhuma instância selecionada</p>
                <Button onClick={handleBack} className="mt-4">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Voltar para Instâncias
                </Button>
              </CardContent>
            </Card>
          </main>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-dark">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title={`QR Code - ${selectedInstance.instanceName}`} />
        <main className="flex flex-1 items-center justify-center p-8">
          <Card className="w-full max-w-md">
            <CardHeader className="items-center text-center">
              <CardTitle>Conexão WhatsApp</CardTitle>
              <CardDescription>
                Instância: <strong>{selectedInstance.instanceName}</strong>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Status Indicator */}
              <div
                className={`flex items-center justify-center gap-2 rounded-lg px-4 py-3 ${statusConfig.bgColor}`}
              >
                {status === 'connecting' && (
                  <Loader2 className={`h-5 w-5 animate-spin ${statusConfig.color}`} />
                )}
                <span className={`font-semibold ${statusConfig.color}`}>
                  {statusConfig.label}
                </span>
              </div>

              {/* Error Message */}
              {error && (
                <div className="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-center text-sm text-error">
                  {error}
                </div>
              )}

              {/* QR Code Display */}
              <div className="flex flex-col items-center justify-center">
                {status === 'connecting' && qrCode ? (
                  <div className="rounded-xl bg-white p-4">
                    {qrCode.startsWith('data:') || qrCode.startsWith('http') ? (
                      <img
                        src={qrCode.startsWith('data:') ? qrCode : `data:image/png;base64,${qrCode}`}
                        alt="QR Code do WhatsApp"
                        className="h-64 w-64"
                      />
                    ) : (
                      <QRCode
                        value={qrCode}
                        size={256}
                        style={{ height: 'auto', maxWidth: '100%', width: '256px' }}
                        viewBox="0 0 256 256"
                      />
                    )}
                  </div>
                ) : status === 'connected' ? (
                  <div className="flex h-64 w-64 flex-col items-center justify-center rounded-xl border-2 border-dashed border-success/30 bg-success/5">
                    <svg
                      className="mb-3 h-16 w-16 text-success"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span className="font-semibold text-success">WhatsApp Conectado!</span>
                    <span className="mt-1 text-sm text-text-muted">
                      Suas mensagens estão ativas
                    </span>
                  </div>
                ) : (
                  <div className="flex h-64 w-64 flex-col items-center justify-center rounded-xl border-2 border-dashed border-border-color bg-hover/30">
                    <svg
                      className="mb-3 h-16 w-16 text-text-muted"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                      />
                    </svg>
                    <span className="text-center text-sm text-text-muted">
                      Clique em &quot;Conectar&quot; para gerar o QR Code
                    </span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-3">
                {status === 'disconnected' && (
                  <Button
                    onClick={handleConnect}
                    disabled={isLoading}
                    className="w-full"
                    size="lg"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        Conectando...
                      </>
                    ) : (
                      'Conectar'
                    )}
                  </Button>
                )}

                {status === 'connecting' && (
                  <Button
                    onClick={handleDisconnect}
                    disabled={isLoading}
                    variant="secondary"
                    className="w-full"
                    size="lg"
                  >
                    Cancelar
                  </Button>
                )}

                {status === 'connected' && (
                  <>
                    <Button
                      onClick={() => router.push(ROUTES.CHAT)}
                      className="w-full"
                      size="lg"
                    >
                      Ir para Chat
                    </Button>
                    <Button
                      onClick={handleDisconnect}
                      disabled={isLoading}
                      variant="secondary"
                      className="w-full"
                      size="lg"
                    >
                      {isLoading ? 'Desconectando...' : 'Desconectar'}
                    </Button>
                  </>
                )}
              </div>

              {/* Back Button */}
              <Button
                onClick={handleBack}
                variant="secondary"
                className="w-full"
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Voltar para Instâncias
              </Button>

              {/* Help Text */}
              {status === 'connecting' && (
                <div className="rounded-lg bg-hover/50 p-4">
                  <h4 className="mb-2 text-sm font-semibold text-text-light">
                    Como conectar:
                  </h4>
                  <ol className="list-inside list-decimal space-y-1 text-sm text-text-muted">
                    <li>Abra o WhatsApp no seu celular</li>
                    <li>Toque em Menu ou Configurações</li>
                    <li>Toque em Aparelhos conectados</li>
                    <li>Toque em Conectar um aparelho</li>
                    <li>Aponte a câmera para este código</li>
                  </ol>
                </div>
              )}
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  )
}
