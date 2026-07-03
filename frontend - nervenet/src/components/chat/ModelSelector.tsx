import React, { useEffect, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { ChevronDown, Cpu, Sparkles, Wand2 } from "lucide-react";

export const ModelSelector: React.FC = () => {
  const { models, selectedModelId, fetchModels, setSelectedModel } = useChat();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Only show Claude models in the dropdown — all other providers are hidden (not deleted)
  const claudeModels = models.filter(m => m.provider === "claude" || m.provider === "anthropic");
  const activeModel = claudeModels.find((m) => m.model_id === selectedModelId)
    ?? claudeModels[0]; // fallback to first Claude model if non-Claude was previously selected

  const handleSelect = (modelId: string, provider: string) => {
    setSelectedModel(modelId, provider);
    setIsOpen(false);
  };

  return (
    <div className="relative z-20">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-secondary/55 border border-border/60 hover:bg-secondary/80 rounded-xl text-sm font-semibold dark:text-white text-gray-800 transition-all focus:outline-none"
      >
        <Sparkles className="w-4 h-4 text-primary animate-pulse" />
        <span>{activeModel?.display_name || "Select Model"}</span>
        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0" onClick={() => setIsOpen(false)} />
          <div className="absolute left-0 mt-2 w-64 dark:bg-[#0e0e11] bg-card border border-border rounded-2xl shadow-2xl p-2 z-30 animate-in fade-in slide-in-from-top-2 duration-150">
            <div className="text-[10px] font-bold text-muted-foreground/60 px-3 py-1.5 uppercase tracking-wider">
              Available Models
            </div>
            
            <div className="max-h-60 overflow-y-auto space-y-1">
              {claudeModels.length === 0 ? (
                <div className="text-xs text-muted-foreground/75 px-3 py-4 text-center">
                  No Claude models available
                </div>
              ) : (
                claudeModels.map((model) => (
                  <button
                    key={model.model_id}
                    onClick={() => handleSelect(model.model_id, model.provider)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left text-sm font-medium transition-all ${
                      selectedModelId === model.model_id
                        ? "bg-primary/10 text-primary border border-primary/20"
                        : "text-muted-foreground hover:bg-secondary/40 dark:hover:text-white hover:text-gray-900"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 shrink-0 text-muted-foreground" />
                      <div className="flex flex-col">
                        <span>{model.display_name}</span>
                        <span className="text-[10px] text-muted-foreground/80 uppercase tracking-tight">{model.provider}</span>
                      </div>
                    </div>
                    {selectedModelId === model.model_id && (
                      <Wand2 className="w-3.5 h-3.5 text-primary shrink-0" />
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
