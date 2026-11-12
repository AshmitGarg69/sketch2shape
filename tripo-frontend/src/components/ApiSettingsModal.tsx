import { useState, useEffect } from "react";
import { 
  getApiBaseUrl, 
  setApiBaseUrl, 
  checkApiHealth, 
  type ApiCapabilities,
  DEFAULT_API_URL 
} from "../services/apiConfig";
import { Sparkles, CheckCircle2, AlertCircle, RefreshCw, X, Server } from "lucide-react";

interface ApiSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApiUpdated?: (newUrl: string) => void;
}

export default function ApiSettingsModal({ isOpen, onClose, onApiUpdated }: ApiSettingsModalProps) {
  const [url, setUrl] = useState(getApiBaseUrl());
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{
    ok: boolean;
    data?: ApiCapabilities;
    error?: string;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      const current = getApiBaseUrl();
      setUrl(current);
      handleTest(current);
    }
  }, [isOpen]);

  const handleTest = async (testUrl = url) => {
    setTesting(true);
    setResult(null);
    const res = await checkApiHealth(testUrl);
    setResult(res);
    setTesting(false);
  };

  const handleSave = () => {
    const clean = setApiBaseUrl(url);
    if (onApiUpdated) onApiUpdated(clean);
    onClose();
  };

  const handleResetDefault = () => {
    setUrl(DEFAULT_API_URL);
    handleTest(DEFAULT_API_URL);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-[#141519] border border-[#2c2e36] rounded-2xl p-6 shadow-2xl text-white">
        
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#23252d]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center text-yellow-400">
              <Server size={18} />
            </div>
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                Kaggle GPU Engine
                <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-yellow-400/10 text-yellow-400 border border-yellow-400/20">
                  Sketch2Shape API
                </span>
              </h3>
              <p className="text-xs text-[#8b8f9a]">Configure your remote GPU backend</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#8b8f9a] hover:text-white hover:bg-[#23252d] transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Input */}
        <div className="mt-4 space-y-3">
          <div>
            <label className="block text-xs font-semibold text-[#8b8f9a] uppercase tracking-wider mb-1.5">
              API Base URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://xxxx.gradio.live"
                className="flex-1 bg-[#1c1e24] border border-[#2c2e36] focus:border-yellow-400 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-white/30 outline-none transition-colors"
              />
              <button
                type="button"
                onClick={() => handleTest()}
                disabled={testing}
                className="px-3.5 py-2.5 rounded-xl bg-[#23252d] hover:bg-[#2e313b] text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw size={13} className={testing ? "animate-spin" : ""} />
                Test
              </button>
            </div>
          </div>

          {/* Test Status Box */}
          <div className="rounded-xl border border-[#2c2e36] bg-[#1a1c22] p-3 text-xs">
            {testing ? (
              <div className="flex items-center gap-2 text-yellow-400 py-1">
                <RefreshCw size={14} className="animate-spin" />
                <span>Checking capabilities & GPU connection...</span>
              </div>
            ) : result?.ok && result.data ? (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                  <CheckCircle2 size={15} />
                  <span>Connected successfully to Kaggle GPU</span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-[#2c2e36]/60 text-[11px] text-[#8b8f9a]">
                  <div>GPU: <b className="text-white">{result.data.gpu}</b></div>
                  <div>VRAM: <b className="text-white">{result.data.vram_gb} GB</b></div>
                  <div>Profile: <b className="text-white">{result.data.profile}</b></div>
                  <div>
                    Backends:{" "}
                    <b className="text-emerald-300">
                      {Object.keys(result.data.backends || {}).join(", ")}
                    </b>
                  </div>
                </div>
              </div>
            ) : result && !result.ok ? (
              <div className="space-y-1 text-red-400">
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertCircle size={15} />
                  <span>Connection failed</span>
                </div>
                <p className="text-[11px] text-red-300/80 break-words">{result.error}</p>
                <p className="text-[11px] text-[#8b8f9a] mt-1">
                  Ensure the Kaggle notebook cell is actively running and Internet is enabled.
                </p>
              </div>
            ) : (
              <div className="text-[#8b8f9a]">
                Click "Test" to check connectivity to your Kaggle Gradio server.
              </div>
            )}
          </div>

          {/* Helper info */}
          <div className="rounded-xl bg-yellow-400/5 border border-yellow-400/10 p-3 text-[11px] text-[#8b8f9a] leading-relaxed">
            <p className="flex items-start gap-1.5">
              <Sparkles size={14} className="text-yellow-400 shrink-0 mt-0.5" />
              <span>
                Kaggle sessions run up to 12 hours. Whenever you re-run the notebook, copy the printed{" "}
                <code className="text-yellow-300 bg-yellow-400/10 px-1 py-0.5 rounded">
                  https://xxxx.gradio.live
                </code>{" "}
                link and paste it here.
              </span>
            </p>
          </div>
        </div>

        {/* Footer actions */}
        <div className="mt-5 pt-4 border-t border-[#23252d] flex items-center justify-between">
          <button
            type="button"
            onClick={handleResetDefault}
            className="text-xs text-[#8b8f9a] hover:text-white transition-colors underline cursor-pointer"
          >
            Reset to default
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-[#8b8f9a] hover:text-white hover:bg-[#23252d] transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-5 py-2 rounded-xl text-xs font-bold bg-yellow-400 hover:bg-yellow-300 text-black transition-colors cursor-pointer shadow-lg shadow-yellow-400/10"
            >
              Save & Apply
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
