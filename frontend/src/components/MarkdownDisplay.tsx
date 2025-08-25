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
  return (
    <div className={className} style={style}>
      <SyntaxHighlighter
        language="markdown"
        style={oneLight}
        customStyle={{
          margin: 0,
          background: 'transparent',
          fontSize: '12px',
          borderRadius: '10px',
          padding: '10px'
        }}
        showLineNumbers={false}
        wrapLines={true}
        wrapLongLines={true}
      >
        {content}
      </SyntaxHighlighter>
    </div>
  )
}

export default MarkdownDisplay
