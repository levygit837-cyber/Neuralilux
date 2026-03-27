'use client'

import { useState, useEffect, useCallback } from 'react'
import QRCode from 'react-qr-code'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { useWhatsappStore, ConnectionStatus } from '@/stores/useWhatsappStore'
import { whatsappService } from '@/services/whatsappService'

const STATUS_CONFIG: Record<
  ConnectionStatus,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  disconnected: {
    label: 'Desconectado',
    color: 'text-error',
    bgColor: 'bg-error/10',
    icon: '●',
  },
  connecting: {
    label: 'Conectando...',
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    icon: '◌',
  },
  connected: {
    label: 'Conectado',
    color: 'text-success',
    bgColor: 'bg-success/10',
    icon: '●',
  },
}

export default function QrPage() {
  const { status, qrCode, isLoading, error, setStatus, setQrCode, setLoading, setError, reset } =
    useWhatsappStore()

  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      setPollingInterval(null)
    }
  }, [pollingInterval])

  const checkStatus = useCallback(async () => {
    try {
      const response = await whatsappService.getStatus()
      setStatus(response.status)
      if (response.status === 'connected') {
        setQrCode(null)
        stopPolling()
      }
    } catch {
      // Silent fail for polling
    }
  }, [setStatus, setQrCode, stopPolling])

  const startPolling = useCallback(() => {
    stopPolling()
    const interval = setInterval(checkStatus, 3000)
    setPollingInterval(interval)
  }, [checkStatus, stopPolling])

  useEffect(() => {
    checkStatus()
    return () => stopPolling()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (status === 'connected') {
      stopPolling()
    }
  }, [status, stopPolling])

  const handleConnect = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await whatsappService.connect()
      setStatus(response.status)

      if (response.status === 'connecting' && response.qrCode) {
        setQrCode(response.qrCode)
      }

      startPolling()

      const qrInterval = setInterval(async () => {
        try {
          const qrResponse = await whatsappService.getQrCode()
          if (qrResponse.qrCode) {
            setQrCode(qrResponse.qrCode)
          }
        } catch {
          // QR might not be ready yet
        }
      }, 3000)

      setTimeout(() => clearInterval(qrInterval), 120000)
    } catch {
      setError('Erro ao conectar. Verifique se o servidor está rodando.')
    } finally {
      setLoading(false)
    }
  }

  const handleDisconnect = async () => {
    setLoading(true)
    setError(null)
    try {
      await whatsappService.disconnect()
      reset()
      stopPolling()
    } catch {
      setError('Erro ao desconectar.')
    } finally {
      setLoading(false)
    }
  }

  const statusConfig = STATUS_CONFIG[status]

  return (
    <div className="flex min-h-screen flex-col bg-dark">
      <Header />
      <main className="flex flex-1 items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader className="items-center text-center">
            <CardTitle>Conexão WhatsApp</CardTitle>
            <CardDescription>
              Escaneie o QR Code com seu WhatsApp para conectar
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Status Indicator */}
            <div
              className={`flex items-center justify-center gap-2 rounded-lg px-4 py-3 ${statusConfig.bgColor}`}
            >
              <span
                className={`${statusConfig.color} text-lg ${
                  status === 'connecting' ? 'animate-pulse' : ''
                }`}
              >
                {statusConfig.icon}
              </span>
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
                    <QRCode
                      value={qrCode}
                      size={256}
                      style={{ height: 'auto', maxWidth: '100%', width: '256px' }}
                      viewBox="0 0 256 256"
                    />
                  ) : (
                    <img
                      src={`data:image/png;base64,${qrCode}`}
                      alt="QR Code do WhatsApp"
                      className="h-64 w-64"
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
                      <svg
                        className="h-5 w-5 animate-spin"
                        viewBox="0 0 24 24"
                        fill="none"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      Conectando...
                    </>
                  ) : (
                    <>
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                        />
                      </svg>
                      Conectar
                    </>
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
                <Button
                  onClick={handleDisconnect}
                  disabled={isLoading}
                  variant="secondary"
                  className="w-full"
                  size="lg"
                >
                  {isLoading ? 'Desconectando...' : 'Desconectar'}
                </Button>
              )}
            </div>

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
  )
}
