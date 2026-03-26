export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Neuralilux</h1>
        <p className="text-xl text-gray-600 mb-8">
          Sistema de Automação WhatsApp com IA
        </p>
        <div className="flex gap-4 justify-center">
          <a
            href="/dashboard"
            className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
          >
            Dashboard
          </a>
          <a
            href="/chat"
            className="px-6 py-3 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition"
          >
            Chat
          </a>
        </div>
      </div>
    </main>
  )
}
