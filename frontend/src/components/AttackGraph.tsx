import React, { useEffect, useRef, useState } from 'react';

interface AttackGraphProps {
  af: {
    ids: string[];
    id2text: Record<string, string>;
    id2atom: Record<string, string>;
    atom2id: Record<string, string>;
    id_attacks: [string, string][];
  } | null;
  semantics: {
    grounded: string[];
    preferred: string[][];
    stable: string[][];
    complete: string[][];
    stage: string[][];
    semi_stable: string[][];
  } | null;
}

export const AttackGraph: React.FC<AttackGraphProps> = ({ af, semantics }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedSemantic, setSelectedSemantic] = useState<string>('none');
  const [selectedExtension, setSelectedExtension] = useState<number>(0);

  useEffect(() => {
    if (!af || !canvasRef.current || !containerRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size to match container
    const container = containerRef.current;
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const { ids, id2text, id_attacks, id2atom, atom2id } = af;
    
    if (ids.length === 0) {
      // Draw "No arguments" message
      ctx.fillStyle = '#6b7280';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('No arguments to display', canvas.width / 2, canvas.height / 2);
      return;
    }

    // Calculate node positions in a circular layout
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(canvas.width, canvas.height) * 0.3;
    const nodePositions: Record<string, { x: number; y: number }> = {};
    
    ids.forEach((id, index) => {
      const angle = (2 * Math.PI * index) / ids.length - Math.PI / 2; // Start from top
      nodePositions[id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      };
    });

    // Determine which nodes are in the selected extension
    const getWinningIds = (): Set<string> => {
      if (!semantics || selectedSemantic === 'none') return new Set();
      
      let extensions: string[][] = [];
      switch (selectedSemantic) {
        case 'grounded':
          extensions = [semantics.grounded];
          break;
        case 'preferred':
          extensions = semantics.preferred;
          break;
        case 'stable':
          extensions = semantics.stable;
          break;
        case 'complete':
          extensions = semantics.complete;
          break;
        case 'stage':
          extensions = semantics.stage;
          break;
        case 'semi_stable':
          extensions = semantics.semi_stable;
          break;
        default:
          return new Set();
      }
      
      if (extensions.length === 0) return new Set();
      
      // Use the selected extension index, or 0 if out of bounds
      const extensionIndex = Math.min(selectedExtension, extensions.length - 1);
      const atomsInExtension = extensions[extensionIndex] || [];
      
      // Convert atoms back to IDs
      return new Set(atomsInExtension.map(atom => atom2id[atom]).filter(Boolean));
    };

    const winningIds = getWinningIds();

    // Draw attack edges first (so they appear behind nodes)
    ctx.strokeStyle = '#dc2626';
    ctx.lineWidth = 2;
    ctx.setLineDash([]);
    
    id_attacks.forEach(([from, to]) => {
      const fromPos = nodePositions[from];
      const toPos = nodePositions[to];
      if (!fromPos || !toPos) return;

      // Draw line
      ctx.beginPath();
      ctx.moveTo(fromPos.x, fromPos.y);
      ctx.lineTo(toPos.x, toPos.y);
      ctx.stroke();

      // Draw arrowhead
      const angle = Math.atan2(toPos.y - fromPos.y, toPos.x - fromPos.x);
      const arrowLength = 10;
      const arrowAngle = Math.PI / 6;

      // Calculate arrow position (slightly before the target node)
      const nodeRadius = 25;
      const arrowX = toPos.x - nodeRadius * Math.cos(angle);
      const arrowY = toPos.y - nodeRadius * Math.sin(angle);

      ctx.beginPath();
      ctx.moveTo(arrowX, arrowY);
      ctx.lineTo(
        arrowX - arrowLength * Math.cos(angle - arrowAngle),
        arrowY - arrowLength * Math.sin(angle - arrowAngle)
      );
      ctx.moveTo(arrowX, arrowY);
      ctx.lineTo(
        arrowX - arrowLength * Math.cos(angle + arrowAngle),
        arrowY - arrowLength * Math.sin(angle + arrowAngle)
      );
      ctx.stroke();
    });

    // Draw nodes
    const nodeRadius = 25;
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ids.forEach((id) => {
      const pos = nodePositions[id];
      if (!pos) return;

      const isWinning = winningIds.has(id);

      // Draw node circle with semantic coloring
      if (isWinning) {
        ctx.fillStyle = '#10b981'; // Green for winning arguments
      } else if (selectedSemantic !== 'none') {
        ctx.fillStyle = '#ef4444'; // Red for losing arguments when semantics are active
      } else {
        ctx.fillStyle = '#4f46e5'; // Default blue
      }
      
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, nodeRadius, 0, 2 * Math.PI);
      ctx.fill();

      // Draw node border
      ctx.strokeStyle = isWinning ? '#065f46' : (selectedSemantic !== 'none' ? '#7f1d1d' : '#1e1b4b');
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw node label
      ctx.fillStyle = 'white';
      ctx.fillText(id, pos.x, pos.y);
    });

    // Draw legend
    ctx.fillStyle = '#374151';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    
    let legendY = 10;
    ctx.fillText('Legend:', 10, legendY);
    legendY += 20;
    
    // Red arrow for attacks
    ctx.strokeStyle = '#dc2626';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(10, legendY);
    ctx.lineTo(40, legendY);
    ctx.stroke();
    
    // Arrow head for legend
    ctx.beginPath();
    ctx.moveTo(40, legendY);
    ctx.lineTo(35, legendY - 3);
    ctx.moveTo(40, legendY);
    ctx.lineTo(35, legendY + 3);
    ctx.stroke();
    
    ctx.fillText('attacks', 45, legendY - 4);
    legendY += 20;

    // Semantic legend if active
    if (selectedSemantic !== 'none') {
      // Green circle for winning
      ctx.fillStyle = '#10b981';
      ctx.beginPath();
      ctx.arc(20, legendY, 8, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = '#065f46';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = '#374151';
      ctx.fillText('winning', 35, legendY - 4);
      legendY += 18;

      // Red circle for losing
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.arc(20, legendY, 8, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = '#7f1d1d';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = '#374151';
      ctx.fillText('losing', 35, legendY - 4);
    }

  }, [af, semantics, selectedSemantic, selectedExtension]);

  // Handle canvas resize
  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current && containerRef.current) {
        const container = containerRef.current;
        const rect = container.getBoundingClientRect();
        canvasRef.current.width = rect.width;
        canvasRef.current.height = rect.height;
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (!af) {
    return (
      <div className="attack-graph-container" ref={containerRef}>
        <div className="graph-placeholder">
          <p className="muted">Attack graph will appear here after analysis</p>
          <p className="muted">Enable "use LLM edges" for complete attack relationships</p>
        </div>
      </div>
    );
  }

  // Get available extensions for the selected semantic
  const getAvailableExtensions = (): string[][] => {
    if (!semantics || selectedSemantic === 'none') return [];
    
    let extensions: string[][] = [];
    switch (selectedSemantic) {
      case 'grounded':
        extensions = [semantics.grounded];
        break;
      case 'preferred':
        extensions = semantics.preferred;
        break;
      case 'stable':
        extensions = semantics.stable;
        break;
      case 'complete':
        extensions = semantics.complete;
        break;
      case 'stage':
        extensions = semantics.stage;
        break;
      case 'semi_stable':
        extensions = semantics.semi_stable;
        break;
      default:
        return [];
    }
    
    // Deduplicate extensions by converting to string and back
    const seen = new Set<string>();
    const deduplicated: string[][] = [];
    
    for (const ext of extensions) {
      const sorted = [...ext].sort();
      const key = JSON.stringify(sorted);
      if (!seen.has(key)) {
        seen.add(key);
        deduplicated.push(ext);
      }
    }
    
    return deduplicated;
  };

  const availableExtensions = getAvailableExtensions();

  return (
    <div className="attack-graph-container" ref={containerRef}>
      {/* Semantic Controls */}
      {semantics && (
        <div className="graph-controls">
          <label>
            Semantic:
            <select 
              value={selectedSemantic} 
              onChange={(e) => {
                setSelectedSemantic(e.target.value);
                setSelectedExtension(0);
              }}
            >
              <option value="none">None (show all)</option>
              <option value="grounded">Grounded</option>
              <option value="preferred">Preferred</option>
              <option value="stable">Stable</option>
              <option value="complete">Complete</option>
              <option value="stage">Stage</option>
              <option value="semi_stable">Semi-stable</option>
            </select>
          </label>
          
          {availableExtensions.length > 1 && (
            <label>
              Extension:
              <select 
                value={selectedExtension} 
                onChange={(e) => setSelectedExtension(parseInt(e.target.value))}
              >
                {availableExtensions.map((_, index) => (
                  <option key={index} value={index}>
                    {index + 1} of {availableExtensions.length}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}
      
      <canvas ref={canvasRef} className="attack-graph-canvas" />
      
      {af.ids.length > 0 && (
        <div className="graph-info">
          <p className="graph-stats">
            {af.ids.length} argument{af.ids.length !== 1 ? 's' : ''}, {af.id_attacks.length} attack{af.id_attacks.length !== 1 ? 's' : ''}
            {selectedSemantic !== 'none' && availableExtensions.length > 0 && (
              <span className="semantic-info">
                {' • '}
                {selectedSemantic}: {availableExtensions[selectedExtension]?.length || 0} winning
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  );
};
