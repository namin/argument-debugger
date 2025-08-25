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
          "background-color": "#4653ff",
          "label": "data(label)",
          "color": "#e8ebf2",
          "text-valign": "center",
          "text-halign": "center",
          "font-size": "11px",
          "width": "label",
          "height": "label",
          "padding": "8px",
          "shape": "round-rectangle",
          "border-width": 1,
          "border-color": "#2b3560"
        }
      },
      { selector: "node[grounded = 1]",
        style: { "background-color": "#4ae39b" }
      },
      { selector: "node.highlight",
        style: { "border-width": 3, "border-color": "#ffd166" }
      },
      { selector: "edge",
        style: {
          "line-color": "#99a1c7",
          "width": 2,
          "target-arrow-color": "#99a1c7",
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

  return <div ref={ref} style={{ width: "100%", height: "480px", borderRadius: 12, border: "1px solid #1f2a44", background:"#0e1426" }} />
}

export default Graph
