import React, { useState, useEffect } from "react";
import { Sparkles } from "lucide-react";

const THINKING_QUOTES = [
  "Addressing user query...",
  "Understanding user intentions...",
  "Consulting Nervenet knowledge base...",
  "Synthesizing relevant context...",
  "Retrieving session memory...",
  "Formulating detailed response...",
  "Aligning model parameters..."
];

export const ThinkingBubble: React.FC = () => {
  const [quoteIndex, setQuoteIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setQuoteIndex((prev) => (prev + 1) % THINKING_QUOTES.length);
    }, 1500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex w-full gap-4 py-6 px-4 md:px-6 border-b border-border/20 bg-secondary/15 animate-in fade-in duration-250 select-none">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center font-bold animate-pulse shrink-0 text-xs">
        N
      </div>
      {/* Content */}
      <div className="flex-1 space-y-3 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold dark:text-white text-gray-800 tracking-tight">
            Nerve net Assistant
          </span>
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-widest flex items-center gap-0.5">
              <Sparkles className="w-2.5 h-2.5 text-primary animate-pulse" /> Thinking
            </span>
          </div>
        </div>

        <div className="space-y-2 mt-1">
          <div className="flex items-center gap-2 text-sm text-primary font-medium italic select-none">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]"></span>
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]"></span>
              <span className="w-2 h-2 rounded-full bg-primary animate-bounce"></span>
            </div>
            <span className="ml-1 text-xs">Nervenet is thinking...</span>
          </div>
          
          <p className="text-xs text-muted-foreground font-semibold animate-pulse transition-all duration-300">
            {THINKING_QUOTES[quoteIndex]}
          </p>
        </div>
      </div>
    </div>
  );
};
