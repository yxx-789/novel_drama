interface MarkdownPreviewProps {
  text: string
  className?: string
}

export default function MarkdownPreview({ text, className = '' }: MarkdownPreviewProps) {
  if (!text.trim()) {
    return <p className="text-xs text-slate-400 italic">暂无内容</p>
  }

  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let key = 0
  let inList = false
  let listItems: React.ReactNode[] = []

  const flushList = () => {
    if (inList && listItems.length > 0) {
      elements.push(
        <ul key={`list-${key++}`} className="list-disc list-inside space-y-1 my-2 text-sm text-slate-700">
          {listItems}
        </ul>
      )
      listItems = []
      inList = false
    }
  }

  const renderInline = (line: string): React.ReactNode => {
    const parts: React.ReactNode[] = []
    let remaining = line
    let idx = 0

    // bold **text**
    while (remaining.length > 0) {
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
      if (boldMatch && boldMatch.index !== undefined) {
        const before = remaining.slice(0, boldMatch.index)
        if (before) parts.push(<span key={`t${idx++}`}>{before}</span>)
        parts.push(
          <strong key={`b${idx++}`} className="font-semibold text-slate-800">
            {boldMatch[1]}
          </strong>
        )
        remaining = remaining.slice(boldMatch.index + boldMatch[0].length)
      } else {
        parts.push(<span key={`t${idx++}`}>{remaining}</span>)
        break
      }
    }
    return parts.length === 1 ? parts[0] : <>{parts}</>
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // horizontal rule
    if (/^---+\s*$/.test(trimmed)) {
      flushList()
      elements.push(<hr key={`hr-${key++}`} className="my-3 border-slate-200" />)
      continue
    }

    // heading
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      flushList()
      const level = headingMatch[1].length
      const content = headingMatch[2]
      const sizes = ['text-lg', 'text-base', 'text-sm', 'text-sm', 'text-xs', 'text-xs']
      const weights = ['font-bold', 'font-semibold', 'font-semibold', 'font-medium', 'font-medium', 'font-medium']
      const margins = ['my-3', 'my-2', 'my-2', 'my-1.5', 'my-1', 'my-1']
      const colors = ['text-slate-900', 'text-slate-800', 'text-slate-700', 'text-slate-700', 'text-slate-600', 'text-slate-600']
      elements.push(
        <h1
          key={`h-${key++}`}
          className={`${sizes[level - 1]} ${weights[level - 1]} ${margins[level - 1]} ${colors[level - 1]}`}
        >
          {renderInline(content)}
        </h1>
      )
      continue
    }

    // blockquote
    if (trimmed.startsWith('>')) {
      flushList()
      const content = trimmed.slice(1).trim()
      elements.push(
        <blockquote key={`bq-${key++}`} className="my-2 pl-3 border-l-2 border-indigo-300 text-sm text-slate-600 italic">
          {renderInline(content)}
        </blockquote>
      )
      continue
    }

    // list item
    if (/^[-+*]\s+/.test(trimmed)) {
      inList = true
      const content = trimmed.replace(/^[-+*]\s+/, '')
      listItems.push(<li key={`li-${key++}`}>{renderInline(content)}</li>)
      continue
    }

    // empty line
    if (trimmed === '') {
      flushList()
      continue
    }

    // paragraph
    flushList()
    elements.push(
      <p key={`p-${key++}`} className="my-1.5 text-sm text-slate-700 leading-relaxed">
        {renderInline(line)}
      </p>
    )
  }

  flushList()

  return <div className={className}>{elements}</div>
}
