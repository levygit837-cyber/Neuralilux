'use client'

import Image from 'next/image'
import { useRouter } from 'next/navigation'
import QRCode from 'react-qr-code'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { useInstanceStore } from '@/stores/useInstanceStore'
import { useResolvedInstance } from '@/hooks/useResolvedInstance'
import { useInstanceConnection } from '@/hooks/useInstanceConnection'
import type { InstanceStatus } from '@/services/instanceService'
import { ROUTES } from '@/lib/constants'
import { ArrowLeft, Loader2 } from 'lucide-react'

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
  const { clearInstance } = useInstanceStore()
  const { resolvedInstance, isResolvingInstance } = useResolvedInstance()
  const { status, qrCode, isLoading, error, connect: handleConnect, disconnect: handleDisconnect } =
    useInstanceConnection(resolvedInstance?.name)

  const handleBack = () => {
    clearInstance()
    router.push(ROUTES.INSTANCES)
  }

  const statusConfig = STATUS_CONFIG[status]

  // No instance selected
  if (isResolvingInstance && !resolvedInstance) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-dark text-text-gray">
        Carregando instância...
      </div>
    )
  }

  if (!resolvedInstance) {
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
        <Header title={`QR Code - ${resolvedInstance.name}`} />
        <main className="flex flex-1 items-center justify-center p-8">
          <Card className="w-full max-w-md">
            <CardHeader className="items-center text-center">
              <CardTitle>Conexão WhatsApp</CardTitle>
              <CardDescription>
                Instância: <strong>{resolvedInstance.name}</strong>
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
                      <Image
                        src={qrCode.startsWith('data:') ? qrCode : `data:image/png;base64,${qrCode}`}
                        alt="QR Code do WhatsApp"
                        width={256}
                        height={256}
                        unoptimized
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
