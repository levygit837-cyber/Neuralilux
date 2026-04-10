const THINKING_SUMMARY_MAX_LENGTH = 140

function truncateAtWordBoundary(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text
  }

  const truncated = text.slice(0, maxLength).trim()
  const lastSpace = truncated.lastIndexOf(' ')
  const safeText = lastSpace > 48 ? truncated.slice(0, lastSpace) : truncated

  return `${safeText.trimEnd()}...`
}

export function buildThinkingSummary(content?: string | null): string {
  const normalizedSource = (content || '')
    .replace(/\r\n/g, '\n')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*[-*]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/^\s*---+\s*$/gm, ' ')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\|/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalizedSource) {
    return 'Resumo do raciocínio disponível para expandir.'
  }

  const sentenceMatch = normalizedSource.match(/.+?[.!?](?:\s|$)/)
  if (sentenceMatch?.[0]) {
    return truncateAtWordBoundary(sentenceMatch[0].trim(), THINKING_SUMMARY_MAX_LENGTH)
  }

  return truncateAtWordBoundary(normalizedSource, THINKING_SUMMARY_MAX_LENGTH)
}
