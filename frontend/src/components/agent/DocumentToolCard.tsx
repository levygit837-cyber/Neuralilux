'use client'

import { useState } from 'react'
import {
  FileText,
  FileJson,
  FileCode,
  File,
  Download,
  CheckCircle2,
  AlertCircle,
  FileType,
  Calendar,
  HardDrive,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentToolEvent } from '@/types/agent'

interface DocumentToolCardProps {
  toolEvent: AgentToolEvent
}

interface DocumentOutput {
  success?: boolean
  document_id?: string
  filename?: string
  file_type?: string
  file_size?: number
  content_base64?: string
  description?: string
  error?: string
}

function getFileIcon(fileType?: string) {
  const type = fileType?.toLowerCase()
  
  switch (type) {
    case 'pdf':
      return File
    case 'json':
      return FileJson
    case 'markdown':
    case 'md':
      return FileCode
    case 'txt':
      return FileText
    default:
      return FileType
  }
}

function getFileExtension(fileType?: string): string {
  const type = fileType?.toLowerCase()
  
  switch (type) {
    case 'pdf':
      return '.pdf'
    case 'json':
      return '.json'
    case 'markdown':
    case 'md':
      return '.md'
    case 'txt':
      return '.txt'
    default:
      return ''
  }
}

function getFileColor(fileType?: string): string {
  const type = fileType?.toLowerCase()
  
  switch (type) {
    case 'pdf':
      return 'text-red-400'
    case 'json':
      return 'text-yellow-400'
    case 'markdown':
    case 'md':
      return 'text-blue-400'
    case 'txt':
      return 'text-gray-400'
    default:
      return 'text-primary'
  }
}

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes === 0) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function formatTimestamp(value?: string): string {
  if (!value) return ''
  
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    
    return date.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

function parseDocumentOutput(toolEvent: AgentToolEvent): DocumentOutput | null {
  if (!toolEvent.outputPayload) return null
  
  if (typeof toolEvent.outputPayload === 'object') {
    return toolEvent.outputPayload as DocumentOutput
  }
  
  try {
    return JSON.parse(String(toolEvent.outputPayload)) as DocumentOutput
  } catch {
    return null
  }
}

function downloadFile(filename: string, contentBase64: string, fileType?: string) {
  try {
    // Decode base64
    const byteCharacters = atob(contentBase64)
    const byteNumbers = new Array(byteCharacters.length)
    
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i)
    }
    
    const byteArray = new Uint8Array(byteNumbers)
    
    // Determine MIME type
    let mimeType = 'application/octet-stream'
    switch (fileType?.toLowerCase()) {
      case 'pdf':
        mimeType = 'application/pdf'
        break
      case 'json':
        mimeType = 'application/json'
        break
      case 'markdown':
      case 'md':
        mimeType = 'text/markdown'
        break
      case 'txt':
        mimeType = 'text/plain'
        break
    }
    
    const blob = new Blob([byteArray], { type: mimeType })
    const url = URL.createObjectURL(blob)
    
    // Create download link
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    // Cleanup
    URL.revokeObjectURL(url)
    
    return true
  } catch (error) {
    console.error('Error downloading file:', error)
    return false
  }
}

export function DocumentToolCard({ toolEvent }: DocumentToolCardProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  
  const output = parseDocumentOutput(toolEvent)
  
  if (!output) {
    return (
      <div className="rounded-2xl border border-white/10 bg-[#120F27]/80 px-4 py-4">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm">Não foi possível carregar informações do documento</span>
        </div>
      </div>
    )
  }
  
  const { 
    success, 
    filename, 
    file_type, 
    file_size, 
    content_base64, 
    description,
    error 
  } = output
  
  const FileIcon = getFileIcon(file_type)
  const fileColor = getFileColor(file_type)
  const canDownload = !!content_base64 && success
  
  const handleDownload = async () => {
    if (!canDownload || !filename || !content_base64) return
    
    setIsDownloading(true)
    setDownloadError(null)
    
    const success = downloadFile(filename, content_base64, file_type)
    
    if (!success) {
      setDownloadError('Erro ao baixar arquivo')
    }
    
    setIsDownloading(false)
  }
  
  // Error state
  if (!success || error) {
    return (
      <div className="rounded-2xl border border-red-500/20 bg-red-500/5 px-4 py-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10">
            <AlertCircle className="h-5 w-5 text-red-400" />
          </div>
          <div className="flex-1">
            <p className="font-medium text-red-200">Falha ao criar documento</p>
            <p className="mt-1 text-sm text-red-300/70">{error || 'Erro desconhecido'}</p>
          </div>
        </div>
      </div>
    )
  }
  
  return (
    <div className="rounded-2xl border border-white/10 bg-[#120F27]/80 px-4 py-4">
      <div className="flex items-start gap-3">
        {/* File Icon */}
        <div className={cn(
          "flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl border",
          file_type === 'pdf' && "border-red-500/30 bg-red-500/10",
          file_type === 'json' && "border-yellow-500/30 bg-yellow-500/10",
          (file_type === 'markdown' || file_type === 'md') && "border-blue-500/30 bg-blue-500/10",
          file_type === 'txt' && "border-gray-500/30 bg-gray-500/10",
          !['pdf', 'json', 'markdown', 'md', 'txt'].includes(file_type || '') && "border-primary/30 bg-primary/10"
        )}>
          <FileIcon className={cn("h-6 w-6", fileColor)} />
        </div>
        
        {/* File Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-text-light truncate">
              {filename || `documento.${file_type}`}
            </p>
            {success && (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
            )}
          </div>
          
          {description && (
            <p className="mt-0.5 text-sm text-text-muted line-clamp-1">
              {description}
            </p>
          )}
          
          {/* Metadata */}
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-gray">
            {file_type && (
              <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 uppercase">
                {file_type}
              </span>
            )}
            
            {file_size !== undefined && file_size > 0 && (
              <span className="inline-flex items-center gap-1">
                <HardDrive className="h-3 w-3" />
                {formatFileSize(file_size)}
              </span>
            )}
            
            {toolEvent.finishedAt && (
              <span className="inline-flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatTimestamp(toolEvent.finishedAt)}
              </span>
            )}
          </div>
        </div>
        
        {/* Download Button */}
        {canDownload && (
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className={cn(
              "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border transition-all",
              "border-border-color bg-dark hover:border-primary/60 hover:bg-hover",
              isDownloading && "opacity-50 cursor-not-allowed"
            )}
            title="Baixar arquivo"
          >
            <Download className={cn(
              "h-4 w-4",
              isDownloading && "animate-bounce"
            )} />
          </button>
        )}
      </div>
      
      {/* Download Error */}
      {downloadError && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          <AlertCircle className="h-4 w-4" />
          {downloadError}
        </div>
      )}
    </div>
  )
}
