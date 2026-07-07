import React, { useEffect, useRef, useCallback, useState, useMemo } from "react";
import { useChat } from "@/hooks/useChat";
import { useSocket } from "@/hooks/useSocket";
import { ModelSelector } from "@/components/chat/ModelSelector";
import logo from "@/assets/logo.png";
import logoLight from "@/assets/logo_light.png";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ThinkingBubble } from "@/components/chat/ThinkingBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { MessageSquareDashed, Download, X, PlusCircle, AlertTriangle, Brain } from "lucide-react";
import api from "@/lib/api";

// ─── Conversation hard limit ────────────────────────────────────────────────
const MAX_MESSAGES = 30; // 15 user + 15 assistant turns per conversation

export const ChatContainer: React.FC = () => {
  const {
    messages,
    currentConversationId,
    isStreaming,
    loading,
    createConversation,
    selectConversation,
    fetchMessages,
  } = useChat();

  const { sendMessage, stopGeneration, isConnected } = useSocket();
  const threadEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef<boolean>(true);

  // Inspector and memory states
  const [showInspector, setShowInspector] = useState(false);
  const [sessionDetails, setSessionDetails] = useState<any>(null);
  const [memKey, setMemKey] = useState("");
  const [memValue, setMemValue] = useState("");

  // Theme observer for switching logo versions
  const [activeTheme, setActiveTheme] = useState<"light" | "dark">(
    document.documentElement.classList.contains("dark") ? "dark" : "light"
  );

  useEffect(() => {
    const handleThemeChange = (e: Event) => {
      const customEvent = e as CustomEvent<"light" | "dark">;
      setActiveTheme(customEvent.detail);
    };
    window.addEventListener("theme-changed", handleThemeChange);

    const observer = new MutationObserver(() => {
      setActiveTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    return () => {
      window.removeEventListener("theme-changed", handleThemeChange);
      observer.disconnect();
    };
  }, []);

  // Load session details containing memory and summary
  useEffect(() => {
    if (!currentConversationId) {
      setSessionDetails(null);
      return;
    }
    const fetchDetails = async () => {
      try {
        const res = await api.get(`/conversations/${currentConversationId}`);
        setSessionDetails(res.data);
      } catch (err) {
        console.error("Failed to load conversation details", err);
      }
    };
    fetchDetails();
  }, [currentConversationId, messages.length]);

  // Prepaid Wallet States
  const [balance, setBalance] = useState<number>(5.00);
  const [totalTokens, setTotalTokens] = useState<number>(0);
  const [showTopUp, setShowTopUp] = useState(false);
  const [topUpAmount, setTopUpAmount] = useState(10);

  const fetchBalance = useCallback(async () => {
    try {
      const res = await api.get("/payment/balance");
      setBalance(res.data.balance);
      setTotalTokens(res.data.total_tokens_used || 0);
    } catch (err) {
      console.error("Fetch balance failed", err);
    }
  }, []);

  useEffect(() => {
    fetchBalance();
  }, [messages.length, fetchBalance]);

  const handleTopUp = async () => {
    try {
      const res = await api.post("/payment/add-funds", { amount: topUpAmount });
      setBalance(res.data.balance);
      alert(`Successfully loaded $${topUpAmount.toFixed(2)} credits to your wallet!`);
      setShowTopUp(false);
    } catch (err) {
      console.error("Top up failed", err);
    }
  };

  // Listen to scroll events to update isAtBottomRef
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150;
      isAtBottomRef.current = isNearBottom;
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Smarter scroll management to avoid layout thrashing and viewport hijacking
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const lastMsg = messages[messages.length - 1];
    const isUserMsg = lastMsg?.role === "user";

    if (isUserMsg || isAtBottomRef.current) {
      // Use instant scroll during streaming to avoid animation fighting and page flickering
      threadEndRef.current?.scrollIntoView({
        behavior: isStreaming && !isUserMsg ? "auto" : "smooth"
      });
    }
  }, [messages, isStreaming]);



  // ─── Derived stats ─────────────────────────────────────────────────────────
  const msgCount = messages.length;
  const isLimitReached = msgCount >= MAX_MESSAGES;
  const limitPercent = Math.min((msgCount / MAX_MESSAGES) * 100, 100);

  // Sum up cost of all assistant messages with telemetry
  const conversationCost = useMemo(() => {
    return messages.reduce((acc, m) => {
      if (m.role === "assistant" && m.metadata?.telemetry?.cost) {
        return acc + m.metadata.telemetry.cost;
      }
      return acc;
    }, 0);
  }, [messages]);

  // Log telemetry info to keep states active and referenced
  if (balance || totalTokens || conversationCost) {
    console.debug("Telemetry stats:", balance, totalTokens, conversationCost);
  }

  // ─── Handlers ──────────────────────────────────────────────────────────────
  const handleSendPrompt = async (prompt: string, attachments: any[]) => {
    if (isLimitReached) return;

    const memoryUpdates: Record<string, any> = {};
    if (memKey.trim() && memValue.trim()) {
      memoryUpdates[memKey.trim()] = memValue.trim();
      setMemKey("");
      setMemValue("");
    }

    const activeId = currentConversationId;
    const finalMemoryUpdates = Object.keys(memoryUpdates).length ? memoryUpdates : undefined;

    if (!activeId) {
      const newConv = await createConversation("New Chat");
      sendMessage(prompt, attachments, newConv.id, finalMemoryUpdates);
    } else {
      sendMessage(prompt, attachments, undefined, finalMemoryUpdates);
    }
  };

  const handleNewConversation = async () => {
    const newConv = await createConversation("New Chat");
    selectConversation(newConv.id);
  };

  const handleRegenerate = useCallback(async () => {
    if (!currentConversationId || messages.length < 2 || isStreaming) return;
    const lastAssistant = messages[messages.length - 1];
    const lastUser = messages[messages.length - 2];
    if (lastAssistant?.role !== "assistant" || lastUser?.role !== "user") return;
    try {
      await api.delete(`/conversations/${currentConversationId}/messages/${lastAssistant.id}`);
      await api.delete(`/conversations/${currentConversationId}/messages/${lastUser.id}`);
      await fetchMessages(currentConversationId);
      sendMessage(lastUser.content, []);
    } catch (e) { console.error("Regenerate failed", e); }
  }, [messages, currentConversationId, isStreaming, sendMessage, fetchMessages]);

  const handleEditSubmit = useCallback(async (messageId: string, newContent: string) => {
    if (!currentConversationId || isStreaming) return;
    const msgIndex = messages.findIndex(m => m.id === messageId);
    if (msgIndex === -1) return;
    try {
      const toDelete = messages.slice(msgIndex).reverse();
      for (const m of toDelete) {
        await api.delete(`/conversations/${currentConversationId}/messages/${m.id}`);
      }
      await fetchMessages(currentConversationId);
      sendMessage(newContent, []);
    } catch (e) { console.error("Edit failed", e); }
  }, [messages, currentConversationId, isStreaming, sendMessage, fetchMessages]);

  const handleExport = () => {
    if (!messages.length) return;
    const md = messages.map(m => {
      const role = m.role === "user" ? "**You**" : `**${m.metadata?.model || "AI"}**`;
      return `${role}\n\n${m.content}`;
    }).join("\n\n---\n\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "conversation.md"; a.click();
    URL.revokeObjectURL(url);
  };





  // Limit bar colour: green → amber → red
  const limitBarColor =
    limitPercent >= 90 ? "bg-red-500" :
      limitPercent >= 70 ? "bg-amber-500" :
        "bg-emerald-500";

  return (
    <div className="flex-1 h-screen flex bg-background select-text overflow-hidden">
      {/* ── Main Chat Column ────────────────────────────────────────── */}
      <div className="flex-1 h-full flex flex-col overflow-hidden border-r border-border/10 relative">
        {/* ── Header ─────────────────────────────────────────────────── */}
        <header className="h-14 border-b border-border/40 bg-card/80 backdrop-blur-md flex items-center justify-between px-6 shrink-0 select-none z-10">
          <div className="flex items-center gap-3">
            <ModelSelector />
            {isConnected ? (
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-500 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full uppercase tracking-wider select-none animate-in fade-in duration-200">
                <span className="relative flex h-1.5 w-1.5 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                </span>
                <span>Online</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-red-500 bg-red-500/10 border border-red-500/20 px-2.5 py-1 rounded-full uppercase tracking-wider select-none animate-in fade-in duration-200">
                <span className="relative flex h-1.5 w-1.5 shrink-0">
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-red-500"></span>
                </span>
                <span>Offline</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Wallet, All-time and This chat badges are hidden as requested */}

            {/* Message counter + progress bar */}
            {currentConversationId && msgCount > 0 && (
              <div className="flex flex-col items-end gap-1 select-none">
                <span className={`text-[9px] font-bold uppercase tracking-wider ${isLimitReached ? "text-red-400" : "text-muted-foreground/70"}`}>
                  {msgCount} / {MAX_MESSAGES} msgs
                </span>
                <div className="w-20 h-1 rounded-full bg-secondary/50 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${limitBarColor}`}
                    style={{ width: `${limitPercent}%` }}
                  />
                </div>
              </div>
            )}

            {messages.length > 0 && (
              <button onClick={handleExport}
                className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-white transition-colors"
                title="Export as Markdown">
                <Download className="w-3.5 h-3.5" /> Export
              </button>
            )}
            {/* {currentConversationId && (
              <button onClick={() => setShowInspector(!showInspector)}
                className={`flex items-center gap-1.5 text-xs font-semibold transition-colors ${showInspector ? "text-primary" : "text-white"}`}
                title="Toggle Session Inspector">
                <Brain className="w-3.5 h-3.5" /> Inspector
              </button>
            )} */}
            {currentConversationId && (
              <button onClick={() => selectConversation(null)}
                className="text-xs font-semibold text-muted-foreground hover:text-white transition-colors">
                Clear
              </button>
            )}
          </div>
        </header>

        {/* ── Messages ───────────────────────────────────────────────── */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
          {!currentConversationId ? (
            <div className="max-w-3xl mx-auto px-4 py-20 flex flex-col items-center justify-center min-h-[calc(100vh-10rem)]">
              <div className="flex flex-col items-center gap-4 text-center select-none animate-in fade-in slide-in-from-bottom-4 duration-300">
                <img src={activeTheme === "dark" ? logo : logoLight} alt="Bharat Smart Services Logo" className="h-12 w-auto object-contain mb-4 select-none" />
                <h1 className="text-4xl font-extrabold dark:text-white text-gray-800 tracking-tight">Nervenet AI</h1>
                <p className="text-muted-foreground max-w-md text-sm mt-2 font-medium">
                  Select a model and start chatting with Nervenet AI. I can build charts, diagrams, dashboards and visualizations — live.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col">
              {messages.length === 0 && loading ? (
                <div className="py-20 flex justify-center">
                  <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                </div>
              ) : messages.length === 0 ? (
                <div className="py-20 text-center text-muted-foreground flex flex-col items-center gap-2">
                  <MessageSquareDashed className="w-10 h-10 text-muted-foreground/40 animate-pulse" />
                  <p className="text-sm font-semibold select-none">Send a message to begin</p>
                </div>
              ) : (
                messages.map((message, index) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    isLast={index === messages.length - 1}
                    isStreaming={isStreaming}
                    onRegenerate={index === messages.length - 1 ? handleRegenerate : undefined}
                    onEditSubmit={message.role === "user" ? (newContent) => handleEditSubmit(message.id, newContent) : undefined}
                    onSendMessage={handleSendPrompt}
                  />
                ))
              )}
              {isStreaming && messages.length > 0 && messages[messages.length - 1].role === "user" && (
                <ThinkingBubble />
              )}
              <div ref={threadEndRef} />
            </div>
          )}
        </div>

        {/* ── Conversation limit reached banner ──────────────────────── */}
        {isLimitReached ? (
          <div className="shrink-0 mx-4 mb-4 p-4 rounded-2xl bg-amber-500/8 border border-amber-500/25 flex items-center justify-between gap-4 animate-in slide-in-from-bottom-4 duration-300">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-amber-500/15 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-bold text-amber-300">Conversation limit reached ({MAX_MESSAGES} messages)</span>
                <span className="text-[10px] text-muted-foreground font-medium mt-0.5">
                  Start a new conversation to keep chatting. This conversation will be saved.
                </span>
              </div>
            </div>
            <button
              onClick={handleNewConversation}
              className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white text-xs font-bold rounded-xl shadow-lg transition-all active:scale-[0.98] shrink-0"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              New Chat
            </button>
          </div>
        ) : (
          <ChatInput onSend={handleSendPrompt} onStop={stopGeneration} />
        )}


      </div>

      {/* ── Context & Memory Inspector Panel ───────────────────────── */}
      {/* {showInspector && (
        <aside className="w-80 h-full dark:bg-[#0d0d11] bg-card flex flex-col overflow-hidden animate-in slide-in-from-right duration-200 z-10 shrink-0 border-l border-border/40">
          <div className="p-4 border-b border-border/30 flex items-center justify-between shrink-0 select-none">
            <span className="text-xs font-bold dark:text-white text-gray-800 uppercase tracking-wider flex items-center gap-1.5">
              🧠 Context & Memory
            </span>
            <button onClick={() => setShowInspector(false)} className="text-muted-foreground hover:text-white transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-5 select-none scrollbar-thin">
            <div className="space-y-1.5">
              <span className="text-[10px] text-muted-foreground uppercase font-black tracking-wider block">Session Info</span>
              <div className="p-3 bg-secondary/10 border border-border/40 rounded-xl space-y-1.5 text-[11px] font-medium dark:text-gray-300 text-gray-600">
                <div>UUID: <code className="text-primary font-bold text-[10px] break-all">{currentConversationId}</code></div>
                <div>Created: <span className="text-gray-400">{sessionDetails?.created_at ? new Date(sessionDetails.created_at).toLocaleString() : "Loading..."}</span></div>
              </div>
            </div>
            
            <div className="space-y-1.5">
              <span className="text-[10px] text-muted-foreground uppercase font-black tracking-wider block">Temporary Memory</span>
              <pre className="p-3 bg-secondary/15 rounded-xl border border-border/50 text-[10px] text-emerald-400 font-mono overflow-x-auto max-h-48 scrollbar-thin">
                {JSON.stringify(sessionDetails?.memory || {}, null, 2)}
              </pre>
            </div>
            
            <div className="space-y-2">
              <span className="text-[10px] text-muted-foreground uppercase font-black tracking-wider block">Inject Memory Update</span>
              <div className="space-y-1.5">
                <input
                  type="text"
                  value={memKey}
                  onChange={(e) => setMemKey(e.target.value)}
                  placeholder="Key (e.g. user_first_name)"
                  className="w-full px-3 py-2 bg-secondary/20 border border-border/60 rounded-xl text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary placeholder-muted-foreground/45"
                />
                <input
                  type="text"
                  value={memValue}
                  onChange={(e) => setMemValue(e.target.value)}
                  placeholder="Value (e.g. Bob)"
                  className="w-full px-3 py-2 bg-secondary/20 border border-border/60 rounded-xl text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary placeholder-muted-foreground/45"
                />
                <p className="text-[10px] text-muted-foreground/80 font-medium leading-relaxed italic">
                  💡 These values will be injected into the conversation context with your next message.
                </p>
              </div>
            </div>
            
            <div className="space-y-1.5">
              <span className="text-[10px] text-muted-foreground uppercase font-black tracking-wider block">Conversation Summary</span>
              <div className="p-3 bg-secondary/10 border border-border/40 rounded-xl text-xs text-muted-foreground font-medium leading-relaxed italic">
                {sessionDetails?.summary || "No summary generated yet. Old history will be condensed once the token threshold is exceeded."}
              </div>
            </div>
          </div>
        </aside>
      )} */}
      {/* ── TOP UP WALLET MODAL ─────────────────────────────────────── */}
      {showTopUp && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
          <div className="bg-[#0a0a0d] border border-border/80 p-6 rounded-2xl w-96 space-y-4 max-w-md select-none">
            <div className="flex items-center justify-between border-b border-border/30 pb-3">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                💰 Top Up Wallet Credits
              </h3>
              <button onClick={() => setShowTopUp(false)} className="text-muted-foreground hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider block">Select Amount to Add</span>
              <div className="grid grid-cols-3 gap-2">
                {[5, 10, 20].map(amt => (
                  <button
                    key={amt}
                    onClick={() => setTopUpAmount(amt)}
                    className={`py-2 text-xs font-bold rounded-xl border transition-all ${topUpAmount === amt
                        ? "bg-primary border-primary text-white"
                        : "bg-secondary/20 border-border/60 hover:bg-secondary/40 text-gray-300"
                      }`}
                  >
                    ${amt}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {[50, 100].map(amt => (
                  <button
                    key={amt}
                    onClick={() => setTopUpAmount(amt)}
                    className={`py-2 text-xs font-bold rounded-xl border transition-all ${topUpAmount === amt
                        ? "bg-primary border-primary text-white"
                        : "bg-secondary/20 border-border/60 hover:bg-secondary/40 text-gray-300"
                      }`}
                  >
                    ${amt}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-3 bg-secondary/10 border border-border/30 rounded-xl space-y-1.5">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-muted-foreground">Gateway Simulator:</span>
                <span className="text-white font-bold uppercase tracking-wide">Stripe Test</span>
              </div>
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-muted-foreground">Charge Amount:</span>
                <span className="text-emerald-400 font-extrabold">${topUpAmount.toFixed(2)}</span>
              </div>
            </div>

            <button
              onClick={handleTopUp}
              className="w-full py-2.5 bg-primary hover:bg-primary/95 text-white font-bold rounded-xl text-xs transition-all active:scale-[0.98]"
            >
              Simulate Stripe Payment
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

