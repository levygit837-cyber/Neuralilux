import type { ReactNode } from 'react'

type ListBuffer = {
  type: 'ul' | 'ol'
  items: string[]
}

type RenderStructuredAgentContentOptions = {
  variant?: 'default' | 'compact' | 'output'
}

function renderInlineSegments(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const inlinePattern = /(\*\*.+?\*\*|`[^`]+`)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let partIndex = 0

  while ((match = inlinePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index))
    }

    const token = match[0]

    if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(
        <strong key={`${keyPrefix}-strong-${partIndex++}`} className="font-semibold text-current">
          {token.slice(2, -2)}
        </strong>
      )
    } else if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${partIndex++}`}
          className="rounded bg-dark/80 px-1.5 py-0.5 font-mono text-[0.92em] text-primary-light"
        >
          {token.slice(1, -1)}
        </code>
      )
    }

    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }

  return nodes.length ? nodes : [text]
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isTableSeparator(line: string): boolean {
  const cells = splitTableRow(line)
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell))
}

function isPotentialTableHeader(line: string): boolean {
  if (!line.includes('|')) {
    return false
  }

  const cells = splitTableRow(line)
  return cells.length > 1 && cells.every((cell) => cell.length > 0)
}

export function renderStructuredAgentContent(
  content: string,
  options?: RenderStructuredAgentContentOptions
): ReactNode[] {
  if (!content) {
    return []
  }

  const normalizedContent = content.replace(/\r\n/g, '\n').trim()
  if (!normalizedContent) {
    return []
  }

  const variant = options?.variant ?? 'default'
  const isCompact = variant === 'compact'
  const isOutput = variant === 'output'
  const lines = normalizedContent.split('\n')
  const elements: ReactNode[] = []
  let paragraphBuffer: string[] = []
  let listBuffer: ListBuffer | null = null
  let keyIndex = 0

  const flushParagraph = () => {
    if (!paragraphBuffer.length) {
      return
    }

    const paragraph = paragraphBuffer.join(' ').trim()
    paragraphBuffer = []

    if (!paragraph) {
      return
    }

    elements.push(
      <p
        key={`paragraph-${keyIndex++}`}
        className={
          isCompact
            ? 'leading-6 break-words text-xs'
            : isOutput
              ? 'break-words text-[12px] leading-6'
              : 'leading-7 break-words'
        }
      >
        {renderInlineSegments(paragraph, `paragraph-${keyIndex}`)}
      </p>
    )
  }

  const flushList = () => {
    if (!listBuffer) {
      return
    }

    const ListTag = listBuffer.type
    elements.push(
      <ListTag
        key={`list-${keyIndex++}`}
        className={
          listBuffer.type === 'ol'
            ? isCompact
              ? 'list-decimal space-y-1.5 pl-4 leading-6 text-xs'
              : isOutput
                ? 'list-decimal space-y-1.5 pl-5 text-[12px] leading-6'
                : 'list-decimal space-y-2 pl-5 leading-7'
            : isCompact
              ? 'list-disc space-y-1.5 pl-4 leading-6 text-xs'
              : isOutput
                ? 'list-disc space-y-1.5 pl-5 text-[12px] leading-6'
                : 'list-disc space-y-2 pl-5 leading-7'
        }
      >
        {listBuffer.items.map((item, itemIndex) => (
          <li key={`list-item-${itemIndex}`} className="break-words">
            {renderInlineSegments(item, `list-${keyIndex}-${itemIndex}`)}
          </li>
        ))}
      </ListTag>
    )
    listBuffer = null
  }

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index]
    const line = rawLine.trim()

    if (!line) {
      flushParagraph()
      flushList()
      continue
    }

    if (line.startsWith('```')) {
      flushParagraph()
      flushList()

      const language = line.slice(3).trim()
      const codeLines: string[] = []
      let cursor = index + 1

      while (cursor < lines.length && !lines[cursor].trim().startsWith('```')) {
        codeLines.push(lines[cursor])
        cursor += 1
      }

      elements.push(
        <div
          key={`code-block-${keyIndex++}`}
          className="overflow-hidden rounded-2xl border border-border-color bg-dark"
        >
          {language && (
            <div
              className={`border-b border-border-color font-semibold uppercase tracking-[0.18em] text-text-muted ${
                isCompact ? 'px-3 py-2 text-[10px]' : isOutput ? 'px-4 py-2 text-[11px]' : 'px-4 py-2 text-xs'
              }`}
            >
              {language}
            </div>
          )}
          <pre
            className={`overflow-x-auto text-text-light ${
              isCompact
                ? 'px-3 py-3 text-[11px] leading-5'
                : isOutput
                  ? 'px-4 py-4 text-[11px] leading-5'
                  : 'px-4 py-4 text-xs leading-6'
            }`}
          >
            <code>{codeLines.join('\n')}</code>
          </pre>
        </div>
      )

      index = cursor < lines.length ? cursor : lines.length
      continue
    }

    if (isPotentialTableHeader(line) && index + 1 < lines.length && isTableSeparator(lines[index + 1].trim())) {
      flushParagraph()
      flushList()

      const headerCells = splitTableRow(line)
      const rows: string[][] = []
      let cursor = index + 2

      while (cursor < lines.length) {
        const candidate = lines[cursor].trim()
        if (!candidate || !candidate.includes('|')) {
          break
        }

        const rowCells = splitTableRow(candidate)
        if (rowCells.length !== headerCells.length) {
          break
        }

        rows.push(rowCells)
        cursor += 1
      }

      elements.push(
        <div key={`table-${keyIndex++}`} className="overflow-x-auto rounded-2xl border border-border-color">
          <table
            className={`min-w-full divide-y divide-border-color text-left ${
              isCompact ? 'text-xs' : isOutput ? 'text-[12px]' : 'text-sm'
            }`}
          >
            <thead className="bg-hover/60">
              <tr>
                {headerCells.map((cell, cellIndex) => (
                  <th
                    key={`table-head-${cellIndex}`}
                    className={`font-semibold text-text-light ${
                      isCompact ? 'px-3 py-2' : isOutput ? 'px-4 py-2.5' : 'px-4 py-3'
                    }`}
                  >
                    {renderInlineSegments(cell, `table-head-${keyIndex}-${cellIndex}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-color bg-dark/40">
              {rows.map((row, rowIndex) => (
                <tr key={`table-row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td
                      key={`table-cell-${rowIndex}-${cellIndex}`}
                      className={`align-top text-text-gray ${
                        isCompact
                          ? 'px-3 py-2 leading-5'
                          : isOutput
                            ? 'px-4 py-2.5 leading-5'
                            : 'px-4 py-3 leading-6'
                      }`}
                    >
                      {renderInlineSegments(cell, `table-cell-${keyIndex}-${rowIndex}-${cellIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

      index = cursor - 1
      continue
    }

    if (/^---+$/.test(line)) {
      flushParagraph()
      flushList()
      elements.push(
        <hr key={`divider-${keyIndex++}`} className="border-border-color/80" />
      )
      continue
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()

      const level = headingMatch[1].length
      const title = headingMatch[2].trim()
      const headingClassMap: Record<number, string> = {
        1:
          isCompact
            ? 'text-base font-semibold text-text-light'
            : isOutput
              ? 'text-xl font-semibold text-text-light'
              : 'text-2xl font-semibold text-text-light',
        2:
          isCompact
            ? 'text-sm font-semibold text-text-light'
            : isOutput
              ? 'text-lg font-semibold text-text-light'
              : 'text-xl font-semibold text-text-light',
        3:
          isCompact
            ? 'text-sm font-semibold text-text-light'
            : isOutput
              ? 'text-base font-semibold text-text-light'
              : 'text-lg font-semibold text-text-light',
        4:
          isCompact
            ? 'text-base font-semibold text-text-light'
            : isOutput
              ? 'text-sm font-semibold text-text-light'
              : 'text-base font-semibold text-text-light',
        5:
          isCompact
            ? 'text-xs font-semibold uppercase tracking-[0.12em] text-text-light'
            : isOutput
              ? 'text-[11px] font-semibold uppercase tracking-[0.12em] text-text-light'
              : 'text-sm font-semibold uppercase tracking-[0.16em] text-text-light',
        6:
          isCompact
            ? 'text-xs font-semibold text-text-gray'
            : isOutput
              ? 'text-[11px] font-semibold text-text-gray'
              : 'text-sm font-semibold text-text-gray',
      }

      elements.push(
        <div key={`heading-${keyIndex++}`} className={headingClassMap[level] || headingClassMap[4]}>
          {renderInlineSegments(title, `heading-${keyIndex}`)}
        </div>
      )
      continue
    }

    const orderedItem = line.match(/^\d+[.)]\s+(.+)$/)
    if (orderedItem) {
      flushParagraph()
      if (!listBuffer || listBuffer.type !== 'ol') {
        flushList()
        listBuffer = { type: 'ol', items: [] }
      }
      listBuffer.items.push(orderedItem[1].trim())
      continue
    }

    const unorderedItem = line.match(/^[-*]\s+(.+)$/)
    if (unorderedItem) {
      flushParagraph()
      if (!listBuffer || listBuffer.type !== 'ul') {
        flushList()
        listBuffer = { type: 'ul', items: [] }
      }
      listBuffer.items.push(unorderedItem[1].trim())
      continue
    }

    flushList()
    paragraphBuffer.push(line)
  }

  flushParagraph()
  flushList()

  return elements
}
