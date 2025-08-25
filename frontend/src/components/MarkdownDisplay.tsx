import React from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface MarkdownDisplayProps {
  content: string
  className?: string
  style?: React.CSSProperties
}

const MarkdownDisplay: React.FC<MarkdownDisplayProps> = ({ 
  content, 
  className = "code", 
  style = {} 
}) => {
  // Convert literal \n strings to actual newlines
  const processedContent = content
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r');

  return (
    <div className={className} style={style}>
      <SyntaxHighlighter
        language="markdown"
        style={{
          ...oneLight,
          'code[class*="language-"]': {
            ...oneLight['code[class*="language-"]'],
            fontSize: '13px',
            lineHeight: '1.5'
          },
          'pre[class*="language-"]': {
            ...oneLight['pre[class*="language-"]'],
            fontSize: '13px',
            lineHeight: '1.5',
            margin: 0,
            padding: '12px'
          },
          // Override inline code styling to be less intrusive
          '.token.code': {
            background: 'rgba(27, 31, 35, 0.05)',
            padding: '0.1em 0.3em',
            borderRadius: '3px',
            fontSize: '0.95em'
          }
        }}
        customStyle={{
          margin: 0,
          background: 'transparent',
          fontSize: '13px',
          borderRadius: '8px',
          padding: '12px',
          lineHeight: '1.5'
        }}
        showLineNumbers={false}
        wrapLines={true}
        wrapLongLines={true}
      >
        {processedContent}
      </SyntaxHighlighter>
    </div>
  )
}

export default MarkdownDisplay
