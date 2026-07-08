import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { D2 } from "@terrastruct/d2";
import { Copy, Check, Sparkles, Terminal, Eye, Code, RotateCcw, Pencil, AlertTriangle } from "lucide-react";
import { Message } from "@/store/chatStore";
import { VegaChart } from "./VegaChart";

// Init D2 once
const d2Instance = new D2();

interface MessageBubbleProps {
  message: Message;
  isLast: boolean;
  isStreaming: boolean;
  onRegenerate?: () => void;
  onEditSubmit?: (newContent: string) => void;
  onSendMessage?: (prompt: string, attachments: any[]) => void;
}

/* ─── D2 Diagram ──────────────────────────────────────────────── */
const D2Diagram: React.FC<{ code: string }> = ({ code }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    
    let isMounted = true;
    const renderD2 = async () => {
      try {
        const result = await d2Instance.compile(code);
        // theme 0 is light, darkTheme 200 is standard dark
        const svg = await d2Instance.render(result.diagram, { theme: 0, darkTheme: 200 });
        if (isMounted && ref.current) {
          ref.current.innerHTML = svg;
        }
      } catch (e: any) {
        if (isMounted) {
          setError(e.message ?? "Diagram error");
        }
      }
    };
    
    renderD2();
    return () => { isMounted = false; };
  }, [code]);

  if (error) return (
    <div className="my-3 p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 text-xs font-mono flex items-start gap-2">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /> {error}
    </div>
  );
  return <div ref={ref} className="my-3 overflow-x-auto rounded-xl bg-[#0d0d10] p-4 border border-border/40 [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-w-full" />;
};

/* ─── BlobIframe ───────────────────────────────────────────────────── */
const BlobIframe: React.FC<{ code: string }> = ({ code }) => {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);
  const [iframeHeight, setIframeHeight] = useState<number>(500);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  useEffect(() => {
    setHasError(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      // Injected stylesheet to force responsive rendering and disable scrollbars without squishing
      const responsiveStyles = `
        <style>
          * { box-sizing: border-box; }
          html, body {
            margin: 0;
            padding: 0;
            width: 100% !important;
            height: auto !important;
            min-height: 100%;
            overflow-y: hidden !important;
            overflow-x: hidden !important;
            background: transparent;
          }
          /* Scale charts and canvas elements proportionally */
          canvas, svg, img {
            max-width: 100% !important;
            height: auto !important;
            display: block;
          }
          /* Target chart containers specifically */
          .chart-container, [class*="chart"], [id*="chart"] {
            width: 100% !important;
            position: relative !important;
          }
        </style>
      `;

      let finalCode = code;
      // Inject inside head, or wrap if head doesn't exist
      if (code.includes("<head>")) {
        finalCode = code.replace("<head>", `<head>${responsiveStyles}`);
      } else if (code.includes("<html>")) {
        finalCode = code.replace("<html>", `<html><head>${responsiveStyles}</head>`);
      } else {
        finalCode = `<html><head>${responsiveStyles}</head><body>${code}</body></html>`;
      }

      const blob = new Blob([finalCode], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      setBlobUrl(prev => { if (prev) URL.revokeObjectURL(prev); return url; });
    }, 600);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [code]);

  const handleIframeLoad = () => {
    if (iframeRef.current) {
      try {
        const doc = iframeRef.current.contentDocument || iframeRef.current.contentWindow?.document;
        if (doc) {
          // Allow some time for charts to render and get height
          setTimeout(() => {
            if (doc.body) {
              const height = doc.body.scrollHeight;
              // Make sure it doesn't collapse below 300px
              setIframeHeight(Math.max(height, 300));
            }
          }, 100);
        }
      } catch (e) {
        console.error("Could not resize iframe", e);
      }
    }
  };

  if (hasError) return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gray-950 text-red-400 min-h-[300px]">
      <AlertTriangle className="w-6 h-6" />
      <p className="text-sm font-semibold">Preview Error</p>
      <p className="text-xs text-gray-500">The generated code has a runtime error</p>
    </div>
  );
  if (!blobUrl) return (
    <div className="w-full h-full min-h-[300px] flex items-center justify-center text-sm text-gray-400 bg-gray-950">
      ⚙️ Rendering preview...
    </div>
  );
  return (
    <iframe
      ref={iframeRef}
      src={blobUrl}
      onLoad={handleIframeLoad}
      className="w-full border-0 overflow-hidden transition-all duration-300"
      style={{ height: `${iframeHeight}px` }}
      scrolling="no"
      title="Preview"
      onError={() => setHasError(true)}
    />
  );
};

/* ─── InlineArtifact ───────────────────────────────────────────────── */
export const InlineArtifact: React.FC<{ code: string; language: string }> = ({ code, language }) => {
  const [tab, setTab] = useState<"preview" | "code">("preview");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-2xl border border-border/40 overflow-hidden shadow-2xl relative w-full bg-white flex flex-col min-h-[300px] h-auto">
      {tab === "preview" ? (
        language === "svg" ? (
          <div className="w-full flex items-center justify-center bg-white overflow-hidden p-4 [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-w-full [&>svg]:object-contain"
            dangerouslySetInnerHTML={{ __html: code }} />
        ) : (
          <BlobIframe code={code} />
        )
      ) : (
        <div className="min-h-[400px] max-h-[600px] overflow-auto bg-[#0a0a0c] p-5">
          <pre className="text-xs font-mono text-emerald-400 leading-relaxed whitespace-pre-wrap">
            <code>{code}</code>
          </pre>
        </div>
      )}
      {/* Absolute Hover Control Zone */}
      <div className="absolute top-0 right-0 w-48 h-14 flex items-center justify-end px-3 select-none z-10 group/toolbar">
        <div className="flex items-center gap-1 bg-black/60 backdrop-blur-md border border-white/10 rounded-xl px-2 py-1 opacity-0 group-hover/toolbar:opacity-100 transition-opacity duration-200 shadow-lg">
          <button onClick={() => setTab("preview")}
            className={`flex items-center gap-1 px-2 py-1 text-[10px] font-bold rounded-lg transition-all ${tab === "preview" ? "bg-white/20 text-white" : "text-white/50 hover:text-white"}`}>
            <Eye className="w-3 h-3" /> Preview
          </button>
          <div className="w-px h-3 bg-white/20" />
          <button onClick={() => setTab("code")}
            className={`flex items-center gap-1 px-2 py-1 text-[10px] font-bold rounded-lg transition-all ${tab === "code" ? "bg-white/20 text-white" : "text-white/50 hover:text-white"}`}>
            <Code className="w-3 h-3" /> Code
          </button>
          <div className="w-px h-3 bg-white/20" />
          <button onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 text-[10px] font-bold text-white/50 hover:text-white rounded-lg transition-all">
            {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
    </div>
  );
};

const PREVIEW_SENTINEL = "::PREVIEW_LOADING::";
const REMARK_PLUGINS = [remarkGfm, remarkMath];
const REHYPE_PLUGINS = [rehypeKatex];

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message, isLast, isStreaming, onRegenerate, onEditSubmit, onSendMessage
}) => {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);

  // Pre-process streaming content: replace any in-progress visual code block with a loading sentinel
  // so ReactMarkdown never renders raw code characters during streaming.
  const processedContent = React.useMemo(() => {
    if (!isLast || !isStreaming || isUser) return message.content;
    let result = message.content;
    // Replace fully-closed visual code blocks (html/svg/mermaid/d2/vega/vegalite) with a sentinel
    result = result.replace(
      /```(html|svg|mermaid|d2|vega|vegalite)[\s\S]*?```/gi,
      PREVIEW_SENTINEL
    );
    // Replace still-open (unclosed) visual blocks — from the ``` to end of string
    result = result.replace(
      /```(html|svg|mermaid|d2|vega|vegalite)[\s\S]*$/i,
      PREVIEW_SENTINEL
    );
    return result;
  }, [message.content, isLast, isStreaming, isUser]);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleEditSave = () => {
    if (editValue.trim() && onEditSubmit) {
      onEditSubmit(editValue.trim());
    }
    setIsEditing(false);
  };

  const markdownComponents = React.useMemo(() => ({
    img: ({ src, alt, ...props }: any) => {
      const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
      const host = apiBase.endsWith("/api") ? apiBase.slice(0, -4) : apiBase;
      const fullSrc = src && src.startsWith("/api/") ? `${host}${src}` : src;
      return <img src={fullSrc} alt={alt}
        className="rounded-2xl border border-border/60 max-w-xl w-full my-4 shadow-2xl animate-in zoom-in-95 duration-300 object-cover"
        {...props} />;
    },
    p: ({ children }: any) => {
      // Render sentinel as a skeleton loading card (not a spinner)
      const text = typeof children === "string" ? children : Array.isArray(children) ? children.join("") : "";
      if (text.includes(PREVIEW_SENTINEL)) {
        return (
          <div className="my-4 rounded-2xl border border-border/40 overflow-hidden shadow-2xl not-prose bg-secondary/10 dark:bg-[#0d0d11]">
            {/* Top progress bar */}
            <div className="h-0.5 bg-border/30 relative overflow-hidden">
              <div className="preview-progress-bar h-full bg-gradient-to-r from-primary via-primary/80 to-primary/40 rounded-full absolute left-0 top-0" />
            </div>

            {/* Header skeleton */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border/20">
              <div className="flex items-center gap-2.5">
                <div className="w-3 h-3 rounded-full skeleton-shimmer opacity-60" />
                <div className="h-2.5 w-28 rounded-full skeleton-shimmer opacity-60" />
              </div>
              <div className="flex gap-1.5">
                <div className="w-2 h-2 rounded-full skeleton-shimmer opacity-40" />
                <div className="w-2 h-2 rounded-full skeleton-shimmer opacity-40" />
                <div className="w-2 h-2 rounded-full skeleton-shimmer opacity-40" />
              </div>
            </div>

            {/* Chart/content skeleton body */}
            <div className="p-5 space-y-4">
              {/* Chart bars skeleton */}
              <div className="flex items-end gap-2 h-28 px-2">
                {[65, 40, 80, 55, 90, 35, 70, 48, 82, 60].map((h, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-t-md skeleton-shimmer opacity-50"
                    style={{ height: `${h}%`, animationDelay: `${i * 0.08}s` }}
                  />
                ))}
              </div>

              {/* X-axis skeleton */}
              <div className="h-px bg-border/30 mx-2" />

              {/* Legend skeleton rows */}
              <div className="space-y-2 pt-1">
                {[70, 50, 85].map((w, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="w-3 h-3 rounded-sm skeleton-shimmer opacity-50" style={{ animationDelay: `${i * 0.15}s` }} />
                    <div className="h-2 rounded-full skeleton-shimmer opacity-40" style={{ width: `${w}%`, animationDelay: `${i * 0.1}s` }} />
                  </div>
                ))}
              </div>
            </div>

            {/* Footer label */}
            <div className="px-5 pb-4 flex items-center gap-2 text-[10px] font-semibold text-muted-foreground/50 tracking-wide uppercase">
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              Generating preview…
            </div>
          </div>
        );
      }
      return <p className="mb-3 last:mb-0">{children}</p>;
    },
    ul: ({ children }: any) => <ul className="list-disc pl-5 mb-3">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal pl-5 mb-3">{children}</ol>,
    li: ({ children }: any) => <li className="mb-1">{children}</li>,
    a: ({ href, children }: any) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{children}</a>,
    table: ({ children }: any) => (
      <div className="overflow-x-auto my-4 rounded-xl border border-border">
        <table className="min-w-full divide-y divide-border dark:bg-[#0e0e11] bg-white">{children}</table>
      </div>
    ),
    thead: ({ children }: any) => <thead className="bg-secondary/20">{children}</thead>,
    tbody: ({ children }: any) => <tbody className="divide-y divide-border">{children}</tbody>,
    tr: ({ children }: any) => <tr>{children}</tr>,
    th: ({ children }: any) => <th className="px-4 py-2 text-left text-xs font-bold dark:text-white text-gray-800 uppercase tracking-wider">{children}</th>,
    td: ({ children }: any) => <td className="px-4 py-2 text-xs dark:text-gray-200 text-gray-800 font-medium">{children}</td>,
    code: ({ className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || "");
      const codeString = String(children).replace(/\n$/, "");
      const isInline = !match;

      if (isInline) return (
        <code className="bg-secondary/50 dark:bg-secondary/15 border border-border/50 dark:text-white text-gray-800 rounded px-1.5 py-0.5 text-xs font-semibold font-mono" {...props}>
          {children}
        </code>
      );

      const lang = match ? match[1].toLowerCase() : "";

      // Vega-Lite visual charts
      const isVegaSpec = (lang === "vega" || lang === "vegalite" || 
                         (lang === "json" && codeString.includes("vega.github.io/schema/vega")));
      if (isVegaSpec) {
        if (isLast && isStreaming) {
          return (
            <div className="my-3 rounded-2xl border border-border/40 overflow-hidden shadow-2xl p-6 bg-secondary/10 flex flex-col items-center justify-center min-h-[150px] space-y-3">
              <div className="w-6 h-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <span className="text-xs font-semibold text-muted-foreground animate-pulse">
                Rendering live chart...
              </span>
            </div>
          );
        }
        return <VegaChart specString={codeString} onSendMessage={onSendMessage} />;
      }

      // Interactive visual artifacts
      if (lang === "html" || lang === "svg" || lang === "mermaid" || lang === "d2") {
        if (isLast && isStreaming) {
          return (
            <div className="my-3 rounded-2xl border border-border/40 overflow-hidden shadow-2xl p-6 bg-secondary/10 flex flex-col items-center justify-center min-h-[150px] space-y-3">
              <div className="w-6 h-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <span className="text-xs font-semibold text-muted-foreground animate-pulse">
                Rendering live preview...
              </span>
            </div>
          );
        }
        if (lang === "mermaid" || lang === "d2") {
          return <D2Diagram code={codeString} />;
        }
        return <InlineArtifact code={codeString} language={lang} />;
      }

      // Standard code block
      return (
        <div className="my-4 rounded-xl border border-border/60 overflow-hidden bg-[#0d0d0f] shadow-lg">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border/55 bg-secondary/15 select-none">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              <Terminal className="w-3.5 h-3.5" />
              <span>{match ? match[1] : "code"}</span>
            </div>
            <button onClick={() => navigator.clipboard.writeText(codeString)}
              className="text-[10px] font-bold text-muted-foreground hover:text-white flex items-center gap-1 transition-colors">
              <Copy className="w-3 h-3" /><span>Copy</span>
            </button>
          </div>
          <pre className="p-4 overflow-x-auto text-xs font-medium font-mono text-emerald-400">
            <code>{codeString}</code>
          </pre>
        </div>
      );
    }
  }), [isLast, isStreaming, onSendMessage]);

  return (
    <div className={`flex w-full gap-4 py-6 px-4 md:px-6 border-b border-border/20 ${isUser ? "bg-background" : "bg-secondary/15"}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border select-none ${
        isUser ? "bg-secondary/80 border-border dark:text-white text-gray-800 text-xs font-bold" : "bg-primary/20 border-primary/30 text-primary"
      }`}>
        {isUser ? "U" : <Sparkles className="w-4 h-4 animate-pulse" />}
      </div>

      {/* Content */}
      <div className="flex-1 space-y-3 min-w-0">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold dark:text-white text-gray-800 tracking-tight">
            {isUser ? "You" : "Nerve net Assistant"}
          </span>
          <div className="flex items-center gap-1">
            {/* User message: edit button */}
            {isUser && onEditSubmit && !isStreaming && (
              <button onClick={() => setIsEditing(true)}
                className="p-1.5 hover:bg-secondary/35 text-muted-foreground hover:text-white rounded-lg transition-all"
                title="Edit message">
                <Pencil className="w-3.5 h-3.5" />
              </button>
            )}
            {/* Assistant: copy + regenerate */}
            {!isUser && message.content && (
              <>
                <button onClick={handleCopy}
                  className="p-1.5 hover:bg-secondary/35 text-muted-foreground hover:text-white rounded-lg transition-all"
                  title="Copy message">
                  {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                </button>
                {isLast && !isStreaming && onRegenerate && (
                  <button onClick={onRegenerate}
                    className="p-1.5 hover:bg-secondary/35 text-muted-foreground hover:text-amber-400 rounded-lg transition-all"
                    title="Regenerate response">
                    <RotateCcw className="w-4 h-4" />
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Editable user message */}
        {isEditing ? (
          <div className="flex flex-col gap-2">
            <textarea
              className="w-full bg-secondary/20 border border-border/60 rounded-xl p-3 text-sm text-white resize-none outline-none focus:border-primary/50 transition-colors"
              rows={3}
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleEditSave(); }}}
              autoFocus
            />
            <div className="flex gap-2">
              <button onClick={handleEditSave}
                className="px-3 py-1.5 bg-primary text-white text-xs font-bold rounded-lg hover:bg-primary/90 transition-all">
                Send
              </button>
              <button onClick={() => { setIsEditing(false); setEditValue(message.content); }}
                className="px-3 py-1.5 bg-secondary/30 text-white text-xs font-bold rounded-lg hover:bg-secondary/50 transition-all">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          /* Markdown Body */
          <div className={`prose dark:prose-invert max-w-none text-sm leading-relaxed dark:text-gray-200 text-gray-800 ${!isUser && isLast && isStreaming ? "typing-cursor" : ""}`}>
            <ReactMarkdown
              remarkPlugins={REMARK_PLUGINS}
              rehypePlugins={REHYPE_PLUGINS}
              components={markdownComponents as any}
            >
              {processedContent}
            </ReactMarkdown>
          </div>
        )}

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {message.attachments.map((file) => (
              <div key={file.id} className="flex items-center gap-1.5 px-3 py-1.5 bg-secondary/40 border border-border/80 rounded-lg text-xs font-semibold dark:text-white text-gray-800">
                <span className="max-w-44 truncate">{file.filename}</span>
                <span className="text-[10px] text-muted-foreground">({(file.file_size / 1024).toFixed(1)} KB)</span>
              </div>
            ))}
          </div>
        )}

        {/* Usage metrics hidden as requested */}
        {/* message.metadata?.telemetry && (
          <div className="flex flex-wrap items-center gap-3 text-[10px] font-bold text-muted-foreground/50 select-none pt-2">
            <span className="uppercase tracking-wide">
              ↑ {message.metadata.telemetry.prompt_tokens} in
            </span>
            <span className="uppercase tracking-wide">
              ↓ {message.metadata.telemetry.completion_tokens} out
            </span>
            {message.metadata.telemetry.cache_read_tokens > 0 && (
              <span className="px-1.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-wide">
                ⚡ {message.metadata.telemetry.cache_read_tokens} cached (−90% cost)
              </span>
            )}
            {message.metadata.telemetry.cost > 0 && (
              <span className="text-violet-400/70 uppercase tracking-wide">
                ${message.metadata.telemetry.cost.toFixed(5)}
              </span>
            )}
          </div>
        ) */}
      </div>
    </div>
  );
};
