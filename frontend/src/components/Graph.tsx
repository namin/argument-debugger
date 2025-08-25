import React, { useEffect, useRef } from "react"
import cytoscape, { ElementDefinition, Stylesheet } from "cytoscape"

type Props = {
  nodes: { id: string; grounded?: boolean; preferred?: string; atom?: string }[]
  edges: { source: string; target: string }[]
  highlightId?: string | null
}

const Graph: React.FC<Props> = ({ nodes, edges, highlightId }) => {
  const ref = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!ref.current) return
    if (cyRef.current) cyRef.current.destroy()

    const elements: ElementDefinition[] = [
      ...nodes.map(n => ({
        data: { id: n.id, label: n.id, grounded: !!n.grounded, atom: n.atom || "" }
      })),
      ...edges.map(e => ({ data: { id: e.source + "->" + e.target, source: e.source, target: e.target } }))
    ]

    const style: Stylesheet[] = [
      { selector: "node",
        style: {
          "background-color": "#e3f2fd",
          "label": "data(label)",
          "color": "#1565c0",
          "text-valign": "center",
          "text-halign": "center",
          "font-size": "11px",
          "width": "label",
          "height": "label",
          "padding": "8px",
          "shape": "round-rectangle",
          "border-width": 2,
          "border-color": "#1976d2"
        }
      },
      { selector: "node[grounded = 1]",
        style: { 
          "background-color": "#e8f5e8", 
          "color": "#2e7d32",
          "border-color": "#4caf50"
        }
      },
      { selector: "node.highlight",
        style: { 
          "border-width": 3, 
          "border-color": "#ff9800",
          "background-color": "#fff3e0"
        }
      },
      { selector: "edge",
        style: {
          "line-color": "#90a4ae",
          "width": 2,
          "target-arrow-color": "#90a4ae",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier"
        }
      }
    ]

    const cy = cytoscape({
      container: ref.current,
      elements,
      style,
      layout: { name: "cose", animate: false },
      wheelSensitivity: 0.2
    })
    cyRef.current = cy

    // fit to container with padding
    cy.resize()
    cy.fit(undefined, 20)

    // grounded flag for styling
    nodes.forEach(n => {
      const node = cy.getElementById(n.id)
      if (node) node.data("grounded", n.grounded ? 1 : 0)
    })

    if (highlightId) {
      cy.getElementById(highlightId).addClass("highlight")
    }

    return () => { cy.destroy() }
  }, [nodes, edges, highlightId])

  return <div ref={ref} style={{ width: "100%", maxWidth: "100%", height: "480px", borderRadius: 12, border: "1px solid #e0e0e0", background:"#ffffff", overflow: "hidden", boxSizing: "border-box" }} />
}

export default Graph
