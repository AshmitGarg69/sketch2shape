import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Pen, Paintbrush, Eraser, 
  Minus, Square, Circle, 
  Undo, Redo, Trash2, Download,
  Palette, Wand2 
} from 'lucide-react';
const COLORS = [
  '#000000', '#FFFFFF', '#EF4444', '#3B82F6', '#10B981', 
  '#EAB308', '#F97316', '#A855F7', '#EC4899', '#6B7280'
];

export default function App() {
  // State
  const [tool, setTool] = useState('pen');
  const [color, setColor] = useState('#000000');
  const [strokeWidth, setStrokeWidth] = useState(3);
  const [opacity, setOpacity] = useState(1.0);
  
  const [history, setHistory] = useState([]);
  const [historyStep, setHistoryStep] = useState(-1);
  const [isDrawing, setIsDrawing] = useState(false);

  // Refs
  const canvasRef = useRef(null);
  const wrapperRef = useRef(null);
  const snapshotRef = useRef(null);
  const startPosRef = useRef({ x: 0, y: 0 });

  // Initialize Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;

    // Set physical resolution of canvas to match wrapper bounds
    const rect = wrapper.getBoundingClientRect();
    // Use a fixed resolution or match container. We match container for 1:1 pixel mapping
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext('2d');
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    // Save initial blank state
    saveHistoryState(canvas);

    // Handle window resize cleanly by just logging, we don't wipe canvas on resize
    // to preserve drawing. For production, complex resize handling (scaling) can be added.
    const handleResize = () => {
      // For simplicity in this demo, canvas size is fixed on first load.
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // History Management
  const saveHistoryState = useCallback((canvasElement) => {
    const ctx = canvasElement.getContext('2d');
    const snapshot = ctx.getImageData(0, 0, canvasElement.width, canvasElement.height);
    
    setHistory(prev => {
      // If we are currently back in time, slice the future history off
      const newHistory = prev.slice(0, historyStep + 1);
      newHistory.push(snapshot);
      return newHistory;
    });
    setHistoryStep(prev => prev + 1);
  }, [historyStep]);

  const handleUndo = () => {
    if (historyStep > 0) {
      const newStep = historyStep - 1;
      restoreHistoryState(newStep);
      setHistoryStep(newStep);
    }
  };

  const handleRedo = () => {
    if (historyStep < history.length - 1) {
      const newStep = historyStep + 1;
      restoreHistoryState(newStep);
      setHistoryStep(newStep);
    }
  };

  const restoreHistoryState = (index) => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.putImageData(history[index], 0, 0);
  };

  const handleClear = () => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    saveHistoryState(canvas);
  };

  const handleDownload = () => {
    const canvas = canvasRef.current;
    
    // Create a temporary canvas to composite the drawing over a white background
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvas.width;
    tempCanvas.height = canvas.height;
    const tCtx = tempCanvas.getContext('2d');
    
    tCtx.fillStyle = '#FFFFFF';
    tCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
    tCtx.drawImage(canvas, 0, 0);
    
    const link = document.createElement('a');
    link.download = 'my-drawing.png';
    link.href = tempCanvas.toDataURL('image/png');
    link.click();
  };

  // Drawing Interaction
  const getCoordinates = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    // Handle both mouse and touch events properly
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: clientX - rect.left,
      y: clientY - rect.top
    };
  };

  const applyContextSettings = (ctx) => {
    ctx.lineWidth = strokeWidth;
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;

    if (tool === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1; // Eraser works better at full opacity
    } else {
      ctx.globalCompositeOperation = 'source-over';
      if (tool === 'brush') {
        ctx.shadowBlur = strokeWidth * 2;
        ctx.shadowColor = color;
      } else {
        ctx.shadowBlur = 0;
      }
    }
  };

  const handlePointerDown = (e) => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const { x, y } = getCoordinates(e);

    setIsDrawing(true);
    startPosRef.current = { x, y };

    // Save snapshot for shapes preview
    snapshotRef.current = ctx.getImageData(0, 0, canvas.width, canvas.height);

    applyContextSettings(ctx);
    ctx.beginPath();
    ctx.moveTo(x, y);

    // To allow drawing a single dot on click
    if (['pen', 'brush', 'eraser'].includes(tool)) {
      ctx.lineTo(x, y);
      ctx.stroke();
    }
  };

  const handlePointerMove = (e) => {
    if (!isDrawing) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const { x, y } = getCoordinates(e);
    const startPos = startPosRef.current;

    if (['line', 'rect', 'circle'].includes(tool)) {
      // Restore previous state for smooth preview without trailing
      ctx.putImageData(snapshotRef.current, 0, 0);
      applyContextSettings(ctx);
      ctx.beginPath();

      if (tool === 'line') {
        ctx.moveTo(startPos.x, startPos.y);
        ctx.lineTo(x, y);
      } else if (tool === 'rect') {
        ctx.rect(startPos.x, startPos.y, x - startPos.x, y - startPos.y);
      } else if (tool === 'circle') {
        const radius = Math.sqrt(
          Math.pow(x - startPos.x, 2) + Math.pow(y - startPos.y, 2)
        );
        ctx.arc(startPos.x, startPos.y, radius, 0, 2 * Math.PI);
      }
      ctx.stroke();
    } else {
      // Freehand drawing
      ctx.lineTo(x, y);
      ctx.stroke();
    }
  };

  const handlePointerUp = () => {
    if (isDrawing) {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      ctx.closePath();
      setIsDrawing(false);
      saveHistoryState(canvas);
    }
  };

  return (
    <div className="h-screen w-full flex overflow-hidden bg-[#050505] text-white font-sans selection:bg-[#FFD83D] selection:text-black">
      
      {/* LEFT SIDEBAR */}
      <aside className="w-[20%] min-w-[280px] h-full bg-[#151515] border-r border-[#292929] flex flex-col overflow-y-auto">
        
        {/* Header */}
        <div className="p-6 border-b border-[#292929]">
         <h1 className="text-xl font-bold tracking-wide flex items-center gap-2">
  <Palette className="text-[#FFD83D] w-6 h-6" />
  Sketch<span className="text-[#FFD83D]">2</span>Shape
</h1>
          <p className="text-xs text-[#A0A0A0] mt-1">Premium Creative Tool</p>
        </div>

        {/* Tools Section */}
        <div className="p-6 border-b border-[#292929]">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-4">Drawing Tools</h2>
          <div className="grid grid-cols-3 gap-3">
            <ToolButton icon={<Pen size={20} />} label="Pen" active={tool === 'pen'} onClick={() => setTool('pen')} />
            <ToolButton icon={<Paintbrush size={20} />} label="Brush" active={tool === 'brush'} onClick={() => setTool('brush')} />
            <ToolButton icon={<Eraser size={20} />} label="Eraser" active={tool === 'eraser'} onClick={() => setTool('eraser')} />
          </div>
        </div>

        {/* Shapes Section */}
        <div className="p-6 border-b border-[#292929]">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-4">Shapes</h2>
          <div className="grid grid-cols-3 gap-3">
            <ToolButton icon={<Minus size={20} />} label="Line" active={tool === 'line'} onClick={() => setTool('line')} />
            <ToolButton icon={<Square size={20} />} label="Rect" active={tool === 'rect'} onClick={() => setTool('rect')} />
            <ToolButton icon={<Circle size={20} />} label="Circle" active={tool === 'circle'} onClick={() => setTool('circle')} />
          </div>
        </div>

        {/* Colors Section */}
        <div className="p-6 border-b border-[#292929]">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-4">Colors</h2>
          <div className="grid grid-cols-5 gap-3">
            {COLORS.map((c) => (
              <button
                key={c}
                onClick={() => setColor(c)}
                className={`w-8 h-8 rounded-full transition-transform hover:scale-110 ${
                  color === c ? 'ring-2 ring-offset-2 ring-[#FFD83D] ring-offset-[#151515]' : 'border border-[#292929]'
                }`}
                style={{ backgroundColor: c }}
                title={c}
              />
            ))}
          </div>
        </div>

        {/* Settings Section */}
        <div className="p-6 flex-1">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-6">Settings</h2>
          
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm text-gray-300">Stroke Thickness</label>
              <span className="text-xs text-[#FFD83D] bg-[#292929] px-2 py-0.5 rounded">{strokeWidth}px</span>
            </div>
            <input 
              type="range" 
              min="1" 
              max="50" 
              value={strokeWidth}
              onChange={(e) => setStrokeWidth(parseInt(e.target.value))}
              className="w-full h-1.5 bg-[#292929] rounded-lg appearance-none cursor-pointer accent-[#FFD83D]"
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm text-gray-300">Opacity</label>
              <span className="text-xs text-[#FFD83D] bg-[#292929] px-2 py-0.5 rounded">{Math.round(opacity * 100)}%</span>
            </div>
            <input 
              type="range" 
              min="0.1" 
              max="1" 
              step="0.1"
              value={opacity}
              onChange={(e) => setOpacity(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#292929] rounded-lg appearance-none cursor-pointer accent-[#FFD83D]"
            />
          </div>
        </div>
      </aside>

      {/* RIGHT CANVAS AREA */}
      <main className="flex-1 relative flex items-center justify-center p-8 bg-[radial-gradient(#292929_1px,transparent_1px)] [background-size:20px_20px]">
        
        {/* Floating Top Toolbar */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-[#111111]/90 backdrop-blur-md border border-[#292929] rounded-2xl p-2 flex items-center gap-2 z-10 shadow-2xl">
          <ActionButton 
            icon={<Undo size={18} />} 
            label="Undo" 
            onClick={handleUndo}
            disabled={historyStep <= 0}
          />
          <ActionButton 
            icon={<Redo size={18} />} 
            label="Redo" 
            onClick={handleRedo}
            disabled={historyStep >= history.length - 1}
          />
          <div className="w-px h-6 bg-[#292929] mx-2" />
          <ActionButton 
            icon={<Trash2 size={18} />} 
            label="Clear" 
            onClick={handleClear} 
            danger
          />
          <div className="w-px h-6 bg-[#292929] mx-2" />
          <ActionButton 
            icon={<Wand2 size={18} />} 
            label="Generate" 
            onClick={handleDownload} /* Change to handleGenerate when you add your API logic */
            highlight
          />
        </div>

        {/* Canvas Container */}
        <div 
          ref={wrapperRef}
          className="w-full h-full max-w-[1200px] max-h-[800px] rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-[#292929] relative bg-white"
        >
          <canvas
            ref={canvasRef}
            className="absolute inset-0 block w-full h-full cursor-crosshair touch-none"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerOut={handlePointerUp} // Stop drawing if mouse leaves canvas
          />
        </div>
      </main>
    </div>
  );
}

// Subcomponents for Sidebar & Toolbar Buttons
function ToolButton({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center justify-center p-3 rounded-xl transition-all duration-200 ${
        active 
          ? 'bg-[#FFD83D] text-black shadow-lg shadow-[#FFD83D]/20 scale-105' 
          : 'bg-[#111111] text-[#A0A0A0] hover:bg-[#292929] hover:text-white'
      }`}
    >
      {icon}
      <span className="text-[10px] font-medium mt-1.5">{label}</span>
    </button>
  );
}

function ActionButton({ icon, label, onClick, disabled, danger, highlight }) {
  let baseClasses = "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ";
  
  if (disabled) {
    baseClasses += "opacity-50 cursor-not-allowed text-[#A0A0A0]";
  } else if (highlight) {
    baseClasses += "bg-[#FFD83D] text-black hover:bg-[#F5C842] shadow-lg shadow-[#FFD83D]/10";
  } else if (danger) {
    baseClasses += "text-[#A0A0A0] hover:bg-red-500/10 hover:text-red-500";
  } else {
    baseClasses += "text-[#A0A0A0] hover:bg-[#292929] hover:text-white";
  }

  return (
    <button onClick={onClick} disabled={disabled} className={baseClasses} title={label}>
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}