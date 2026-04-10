'use client'

import { useState, useEffect, useCallback } from 'react'
import { agentService } from '@/services/agentService'

interface Model {
  id: string
  name: string
  provider: string
}

interface UseModelsReturn {
  models: Model[]
  currentModel: Model | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

export function useModels(): UseModelsReturn {
  const [models, setModels] = useState<Model[]>([])
  const [currentModel, setCurrentModel] = useState<Model | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchModels = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Buscar modelos disponíveis
      const modelsResponse = await agentService.getModels()
      
      if (modelsResponse.error) {
        // Se houver erro, não definimos erro, apenas usamos o modelo atual
        console.warn('Models fetch warning:', modelsResponse.error)
      }
      
      setModels(modelsResponse.models || [])

      // Buscar modelo atual configurado
      try {
        const currentResponse = await agentService.getCurrentModel()
        setCurrentModel(currentResponse)
      } catch (currentErr) {
        console.warn('Failed to fetch current model:', currentErr)
        // Se falhar, usar o primeiro modelo da lista ou fallback
        if (modelsResponse.models && modelsResponse.models.length > 0) {
          setCurrentModel(modelsResponse.models[0])
        } else {
          setCurrentModel({
            id: 'local-model',
            name: 'Local Model',
            provider: 'lm_studio',
          })
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch models'
      setError(errorMessage)
      
      // Fallback quando não conseguir conectar
      setCurrentModel({
        id: 'local-model',
        name: 'Local Model',
        provider: 'lm_studio',
      })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchModels()
  }, [fetchModels])

  return {
    models,
    currentModel,
    isLoading,
    error,
    refetch: fetchModels,
  }
}
