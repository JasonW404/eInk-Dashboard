import { useMemo } from 'react'
import { marked } from 'marked'

interface TextStyle {
  text: string
  textAlign: 'left' | 'center' | 'right'
  horizontalAlign: 'left' | 'center' | 'right'
  verticalAlign: 'top' | 'center' | 'bottom'
  paddingTop: number
  paddingBottom: number
  paddingLeft: number
  paddingRight: number
}

function parseParams(): TextStyle {
  const params = new URLSearchParams(window.location.search)
  return {
    text: params.get('text') ?? '',
    textAlign: (params.get('textAlign') as TextStyle['textAlign']) || 'center',
    horizontalAlign: (params.get('horizontalAlign') as TextStyle['horizontalAlign']) || 'center',
    verticalAlign: (params.get('verticalAlign') as TextStyle['verticalAlign']) || 'center',
    paddingTop: params.get('paddingTop') !== null ? Number(params.get('paddingTop')) : 20,
    paddingBottom: params.get('paddingBottom') !== null ? Number(params.get('paddingBottom')) : 20,
    paddingLeft: params.get('paddingLeft') !== null ? Number(params.get('paddingLeft')) : 20,
    paddingRight: params.get('paddingRight') !== null ? Number(params.get('paddingRight')) : 20,
  }
}

export function TextPageDisplay() {
  const style = useMemo(parseParams, [])
  const html = useMemo(() => {
    try { return marked.parse(style.text, { async: false }) as string } catch { return style.text }
  }, [style.text])

  const containerStyle: React.CSSProperties = {
    width: 800,
    height: 480,
    padding: `${style.paddingTop}px ${style.paddingRight}px ${style.paddingBottom}px ${style.paddingLeft}px`,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: style.verticalAlign === 'top' ? 'flex-start' : style.verticalAlign === 'bottom' ? 'flex-end' : 'center',
    alignItems: style.horizontalAlign === 'left' ? 'flex-start' : style.horizontalAlign === 'right' ? 'flex-end' : 'center',
    background: '#fff',
    fontFamily: "'JetBrains Mono', monospace",
    boxSizing: 'border-box',
  }

  const contentStyle: React.CSSProperties = {
    textAlign: style.textAlign,
    width: '100%',
    color: '#000',
  }

  return (
    <main className="eink-display" data-eink-ready="true" style={containerStyle}>
      <div className="text-page-content" style={contentStyle} dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  )
}
