import { useState, useRef, useEffect, type ChangeEvent } from 'react';
import { 
  Pen, Paintbrush, Eraser, 
  Minus, Square, Circle, 
  Undo, Redo, Trash2, Download,
  Palette, Wand2, Upload, FilePlus
} from 'lucide-react';

const COLORS = [
  '#000000', '#FFFFFF', '#EF4444', '#3B82F6', '#10B981', 
  '#EAB308', '#F97316', '#A855F7', '#EC4899', '#6B7280'
];

export interface ScribblePageProps {
  onGenerate?: () => void;
  onBackToMain?: () => void;
}

export default function ModernCanvasApplication({ onGenerate, onBackToMain }: ScribblePageProps) {
  // Tool & style state
  const [tool, setTool] = useState<'pen' | 'brush' | 'eraser' | 'line' | 'rect' | 'circle'>('pen');
  const [color, setColor] = useState('#000000');
  const [strokeWidth, setStrokeWidth] = useState(4);
  const [opacity, setOpacity] = useState(1.0);

  // History state for buttons
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Refs for canvas & drawing
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const historyRef = useRef<ImageData[]>([]);
  const historyStepRef = useRef<number>(-1);

  const isDrawingRef = useRef(false);
  const startPosRef = useRef({ x: 0, y: 0 });
  const lastPosRef = useRef({ x: 0, y: 0 });
  const snapshotRef = useRef<ImageData | null>(null);

  // History management
  const pushHistory = (canvasElement: HTMLCanvasElement) => {
    const ctx = canvasElement.getContext('2d');
    if (!ctx) return;
    const snapshot = ctx.getImageData(0, 0, canvasElement.width, canvasElement.height);

    const nextHistory = historyRef.current.slice(0, historyStepRef.current + 1);
    nextHistory.push(snapshot);
    if (nextHistory.length > 30) {
      nextHistory.shift();
    }
    historyRef.current = nextHistory;
    historyStepRef.current = nextHistory.length - 1;
    setCanUndo(historyStepRef.current > 0);
    setCanRedo(false);
  };

  const handleUndo = () => {
    if (historyStepRef.current > 0) {
      historyStepRef.current -= 1;
      restoreHistory(historyStepRef.current);
      setCanUndo(historyStepRef.current > 0);
      setCanRedo(true);
    }
  };

  const handleRedo = () => {
    if (historyStepRef.current < historyRef.current.length - 1) {
      historyStepRef.current += 1;
      restoreHistory(historyStepRef.current);
      setCanUndo(true);
      setCanRedo(historyStepRef.current < historyRef.current.length - 1);
    }
  };

  const restoreHistory = (index: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const snapshot = historyRef.current[index];
    if (!ctx || !snapshot) return;
    ctx.putImageData(snapshot, 0, 0);
  };

  const clearToBlank = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    pushHistory(canvas);
    sessionStorage.removeItem('sketch2shape_drawing');
    sessionStorage.setItem('sketch2shape_mode', 'scratch');
  };

  const drawImageToCanvas = (dataUrl: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const img = new Image();
    img.onload = () => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      const s = Math.min((canvas.width * 0.9) / img.width, (canvas.height * 0.9) / img.height);
      const dx = (canvas.width - img.width * s) / 2;
      const dy = (canvas.height - img.height * s) / 2;
      ctx.drawImage(img, dx, dy, img.width * s, img.height * s);
      pushHistory(canvas);
      sessionStorage.setItem('sketch2shape_drawing', dataUrl);
      sessionStorage.setItem('sketch2shape_mode', 'image');
    };
    img.src = dataUrl;
  };

  const handleImportFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        drawImageToCanvas(reader.result);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  // Initialize Canvas ONCE on mount
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;

    const rect = wrapper.getBoundingClientRect();
    const width = Math.max(800, Math.floor(rect.width));
    const height = Math.max(600, Math.floor(rect.height));
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, width, height);
    }

    const mode = sessionStorage.getItem('sketch2shape_mode');
    const savedDrawing = sessionStorage.getItem('sketch2shape_drawing');

    // If explicit mode is scratch, start completely blank
    if (mode === 'scratch' || !savedDrawing) {
      pushHistory(canvas);
    } else {
      // Load saved drawing once
      const img = new Image();
      img.onload = () => {
        if (!canvas) return;
        const cCtx = canvas.getContext('2d');
        if (!cCtx) return;
        cCtx.fillStyle = '#FFFFFF';
        cCtx.fillRect(0, 0, canvas.width, canvas.height);
        const s = Math.min((canvas.width * 0.9) / img.width, (canvas.height * 0.9) / img.height);
        const dx = (canvas.width - img.width * s) / 2;
        const dy = (canvas.height - img.height * s) / 2;
        cCtx.drawImage(img, dx, dy, img.width * s, img.height * s);
        pushHistory(canvas);
      };
      img.src = savedDrawing;
    }
  }, []); // Strictly empty dependency array so it never re-initializes on history or stroke change!

  // Coordinate scaling to match physical canvas pixels
  const getCoordinates = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  const applyContextSettings = (ctx: CanvasRenderingContext2D) => {
    ctx.lineWidth = strokeWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (tool === 'eraser') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = '#FFFFFF';
      ctx.fillStyle = '#FFFFFF';
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = opacity;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      if (tool === 'brush') {
        ctx.shadowBlur = strokeWidth * 1.5;
        ctx.shadowColor = color;
      } else {
        ctx.shadowBlur = 0;
      }
    }
  };

  // Drawing event handlers
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch (_) {}

    const { x, y } = getCoordinates(e);
    isDrawingRef.current = true;
    startPosRef.current = { x, y };
    lastPosRef.current = { x, y };

    snapshotRef.current = ctx.getImageData(0, 0, canvas.width, canvas.height);
    applyContextSettings(ctx);

    if (['pen', 'brush', 'eraser'].includes(tool)) {
      ctx.beginPath();
      ctx.arc(x, y, strokeWidth / 2, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDrawingRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { x, y } = getCoordinates(e);
    const startPos = startPosRef.current;
    const lastPos = lastPosRef.current;

    applyContextSettings(ctx);

    if (['line', 'rect', 'circle'].includes(tool)) {
      if (snapshotRef.current) {
        ctx.putImageData(snapshotRef.current, 0, 0);
      }
      ctx.beginPath();
      if (tool === 'line') {
        ctx.moveTo(startPos.x, startPos.y);
        ctx.lineTo(x, y);
      } else if (tool === 'rect') {
        ctx.rect(startPos.x, startPos.y, x - startPos.x, y - startPos.y);
      } else if (tool === 'circle') {
        const radius = Math.hypot(x - startPos.x, y - startPos.y);
        ctx.arc(startPos.x, startPos.y, radius, 0, Math.PI * 2);
      }
      ctx.stroke();
    } else {
      // Freehand drawing: draw smooth connected segments
      ctx.beginPath();
      ctx.moveTo(lastPos.x, lastPos.y);
      ctx.lineTo(x, y);
      ctx.stroke();
      lastPosRef.current = { x, y };
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDrawingRef.current) return;
    isDrawingRef.current = false;

    try {
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    } catch (_) {}

    const canvas = canvasRef.current;
    if (canvas) {
      pushHistory(canvas);
    }
  };

  const handleDownload = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = 'my-drawing.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const handleGenerate = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      try {
        const dataUrl = canvas.toDataURL('image/png');
        sessionStorage.setItem('sketch2shape_drawing', dataUrl);
        sessionStorage.setItem('sketch2shape_ask_prompt', 'true');
        sessionStorage.removeItem('sketch2shape_autogen');
      } catch (err) {
        console.error('Failed to export canvas image:', err);
      }
    }
    if (onGenerate) {
      onGenerate();
    } else {
      window.history.pushState({}, '', '/final');
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  };

  return (
    <div className="h-screen w-full flex overflow-hidden bg-[#050505] text-white font-sans selection:bg-[#FFD83D] selection:text-black">
      
      {/* LEFT SIDEBAR */}
      <aside className="w-[22%] min-w-[280px] h-full bg-[#151515] border-r border-[#292929] flex flex-col overflow-y-auto">
        
        {/* Header */}
        <div className="p-6 border-b border-[#292929]">
          <h1 
            onClick={onBackToMain}
            className="text-xl font-bold tracking-wide flex items-center gap-2 cursor-pointer hover:opacity-90 transition-opacity"
            title="Go to Hero / Main Menu"
          >
            <Palette className="text-[#FFD83D] w-6 h-6" />
            Sketch<span className="text-[#FFD83D]">2</span>Shape
          </h1>
          <p className="text-xs text-[#A0A0A0] mt-1">Creative Scribble Studio</p>
          {onBackToMain && (
            <button
              onClick={onBackToMain}
              className="mt-3 text-xs text-[#FFD83D] hover:underline flex items-center gap-1 cursor-pointer transition-colors"
            >
              ← Back to Main Menu
            </button>
          )}
        </div>

        {/* Canvas Mode Options: Scratch vs Continue on Image */}
        <div className="p-5 border-b border-[#292929] flex flex-col gap-2">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-1">Canvas Mode</h2>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={clearToBlank}
              title="Start with a fresh blank canvas to draw from scratch"
              className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl bg-[#222] hover:bg-[#333] text-[11px] font-medium text-white transition-colors cursor-pointer border border-[#333]"
            >
              <FilePlus size={14} className="text-[#FFD83D]" />
              Scratch
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              title="Import or continue drawing on an image"
              className="flex items-center justify-center gap-1.5 py-2 px-2.5 rounded-xl bg-[#222] hover:bg-[#333] text-[11px] font-medium text-white transition-colors cursor-pointer border border-[#333]"
            >
              <Upload size={14} className="text-[#FFD83D]" />
              Add Image
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={handleImportFile}
          />
        </div>

        {/* Drawing Tools */}
        <div className="p-5 border-b border-[#292929]">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-3">Drawing Tools</h2>
          <div className="grid grid-cols-3 gap-2.5">
            <ToolButton icon={<Pen size={18} />} label="Pen" active={tool === 'pen'} onClick={() => setTool('pen')} />
            <ToolButton icon={<Paintbrush size={18} />} label="Brush" active={tool === 'brush'} onClick={() => setTool('brush')} />
            <ToolButton icon={<Eraser size={18} />} label="Eraser" active={tool === 'eraser'} onClick={() => setTool('eraser')} />
          </div>
        </div>

        {/* Shapes Section */}
        <div className="p-5 border-b border-[#292929]">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-3">Shapes</h2>
          <div className="grid grid-cols-3 gap-2.5">
            <ToolButton icon={<Minus size={18} />} label="Line" active={tool === 'line'} onClick={() => setTool('line')} />
            <ToolButton icon={<Square size={18} />} label="Rect" active={tool === 'rect'} onClick={() => setTool('rect')} />
            <ToolButton icon={<Circle size={18} />} label="Circle" active={tool === 'circle'} onClick={() => setTool('circle')} />
          </div>
        </div>

        {/* Colors Section */}
        <div className="p-5 border-b border-[#292929]">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-3">Colors</h2>
          <div className="grid grid-cols-5 gap-2.5">
            {COLORS.map((c) => (
              <button
                key={c}
                onClick={() => setColor(c)}
                className={`w-7 h-7 rounded-full transition-transform hover:scale-110 cursor-pointer ${
                  color === c ? 'ring-2 ring-offset-2 ring-[#FFD83D] ring-offset-[#151515]' : 'border border-[#333]'
                }`}
                style={{ backgroundColor: c }}
                title={c}
              />
            ))}
          </div>
        </div>

        {/* Stroke & Opacity Settings */}
        <div className="p-5 flex-1">
          <h2 className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider mb-4">Settings</h2>
          
          <div className="mb-5">
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs text-gray-300">Stroke Thickness</label>
              <span className="text-[11px] text-[#FFD83D] bg-[#292929] px-2 py-0.5 rounded font-mono">{strokeWidth}px</span>
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
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-xs text-gray-300">Opacity</label>
              <span className="text-[11px] text-[#FFD83D] bg-[#292929] px-2 py-0.5 rounded font-mono">{Math.round(opacity * 100)}%</span>
            </div>
            <input 
              type="range" 
              min="0.1" 
              max="1" 
              step="0.05" 
              value={opacity}
              onChange={(e) => setOpacity(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#292929] rounded-lg appearance-none cursor-pointer accent-[#FFD83D]"
            />
          </div>
        </div>
      </aside>

      {/* RIGHT CANVAS AREA */}
      <main className="flex-1 relative flex items-center justify-center p-6 bg-[radial-gradient(#292929_1px,transparent_1px)] [background-size:20px_20px] select-none">
        
        {/* Floating Top Toolbar */}
        <div className="absolute top-5 left-1/2 -translate-x-1/2 bg-[#111111]/95 backdrop-blur-md border border-[#292929] rounded-2xl p-2 flex items-center gap-2 z-10 shadow-2xl">
          <ActionButton 
            icon={<Undo size={17} />} 
            label="Undo" 
            onClick={handleUndo}
            disabled={!canUndo}
          />
          <ActionButton 
            icon={<Redo size={17} />} 
            label="Redo" 
            onClick={handleRedo}
            disabled={!canRedo}
          />
          <div className="w-px h-6 bg-[#292929] mx-1" />
          <ActionButton 
            icon={<Trash2 size={17} />} 
            label="Clear" 
            onClick={clearToBlank} 
            danger
          />
          <ActionButton 
            icon={<Download size={17} />} 
            label="Save PNG" 
            onClick={handleDownload} 
          />
          <div className="w-px h-6 bg-[#292929] mx-1" />
          <ActionButton 
            icon={<Wand2 size={17} />} 
            label="Generate" 
            onClick={handleGenerate}
            highlight
          />
        </div>

        {/* Canvas Container */}
        <div 
          ref={wrapperRef}
          className="w-full h-full max-w-[1200px] max-h-[820px] rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-[#292929] relative bg-white touch-none"
        >
          <canvas
            ref={canvasRef}
            className="absolute inset-0 block w-full h-full cursor-crosshair touch-none"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerUp}
          />
        </div>
      </main>
    </div>
  );
}

// Subcomponents for Sidebar & Toolbar Buttons
interface ToolButtonProps {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}

function ToolButton({ icon, label, active, onClick }: ToolButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center justify-center p-2.5 rounded-xl transition-all duration-200 cursor-pointer ${
        active 
          ? 'bg-[#FFD83D] text-black shadow-lg shadow-[#FFD83D]/20 scale-105 font-medium' 
          : 'bg-[#1a1a1a] text-[#A0A0A0] hover:bg-[#292929] hover:text-white'
      }`}
    >
      {icon}
      <span className="text-[10px] mt-1">{label}</span>
    </button>
  );
}

interface ActionButtonProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  highlight?: boolean;
}

function ActionButton({ icon, label, onClick, disabled = false, danger = false, highlight = false }: ActionButtonProps) {
  let baseClasses = "flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all duration-200 cursor-pointer ";
  
  if (disabled) {
    baseClasses += "opacity-40 cursor-not-allowed text-[#A0A0A0]";
  } else if (highlight) {
    baseClasses += "bg-[#FFD83D] text-black hover:bg-[#F5C842] shadow-lg shadow-[#FFD83D]/10 font-semibold";
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
