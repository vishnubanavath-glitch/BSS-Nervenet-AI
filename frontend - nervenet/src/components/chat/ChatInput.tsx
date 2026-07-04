import React, { useRef, useState, useCallback, useEffect } from "react";
import { Paperclip, Send, Square, X, Mic, MicOff } from "lucide-react";
import { useChat } from "@/hooks/useChat";

interface ChatInputProps {
  onSend: (prompt: string, attachments: any[]) => void;
  onStop: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, onStop }) => {
  const { isStreaming, uploadAttachment } = useChat();
  const [prompt, setPrompt] = useState("");
  const [attachments, setAttachments] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [micUnavailable, setMicUnavailable] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // Set up SpeechRecognition
  useEffect(() => {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      setMicUnavailable(true);
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    let finalTranscript = "";

    recognition.onstart = () => {
      setIsListening(true);
      finalTranscript = "";
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      setPrompt(finalTranscript + interim);
      adjustHeight();
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed") {
        setMicUnavailable(true);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
    };
  }, []);

  const toggleMic = useCallback(() => {
    const rec = recognitionRef.current;
    if (!rec) return;

    if (isListening) {
      rec.stop();
    } else {
      try {
        rec.start();
      } catch (e) {
        console.error("Mic start failed", e);
      }
    }
  }, [isListening]);

  const adjustHeight = () => {
    const tx = textareaRef.current;
    if (tx) {
      tx.style.height = "auto";
      tx.style.height = `${Math.min(tx.scrollHeight, 200)}px`;
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setPrompt(e.target.value);
    adjustHeight();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const targetFile = files[0];

    const attachmentData = await uploadAttachment(targetFile);
    if (attachmentData) {
      setAttachments((prev) => [...prev, attachmentData]);
    }
    setUploading(false);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleSend = () => {
    if (!prompt.trim() && attachments.length === 0) return;
    if (isStreaming) return;

    // Stop mic if still listening
    if (isListening) recognitionRef.current?.stop();

    onSend(prompt, attachments);
    setPrompt("");
    setAttachments([]);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className="p-4 border-t border-border/40 bg-background max-w-4xl mx-auto w-full">
      {/* File Previews */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3 px-2">
          {attachments.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-secondary/60 border border-border rounded-xl text-xs font-semibold dark:text-white text-gray-800 select-none animate-in fade-in zoom-in-95 duration-150"
            >
              <span className="truncate max-w-44">{file.name}</span>
              <button
                onClick={() => removeAttachment(file.id)}
                className="p-0.5 hover:bg-secondary rounded text-muted-foreground hover:text-foreground transition-all"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Mic listening indicator */}
      {isListening && (
        <div className="flex items-center gap-2 mb-2 px-2 text-xs font-semibold text-primary animate-pulse">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
          Listening... speak now
        </div>
      )}

      {/* Input container */}
      <div className={`relative flex items-end gap-2 p-2 bg-secondary/35 border rounded-2xl focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/45 transition-all ${isListening ? "border-red-500/60" : "border-border/60"}`}>
        {/* Attachment upload trigger */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          className="hidden"
          accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.xls,.json,.md,.py,.js,.ts,.yaml,.yml,image/*"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || isStreaming}
          className="p-2.5 hover:bg-secondary/45 text-muted-foreground hover:text-foreground rounded-xl transition-all disabled:opacity-40"
          title="Attach file (PDF, DOCX, images, spreadsheets, code…)"
        >
          {uploading ? (
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
          ) : (
            <Paperclip className="w-5 h-5" />
          )}
        </button>

        {/* Dynamic expanding textarea */}
        <textarea
          ref={textareaRef}
          rows={1}
          value={prompt}
          onChange={handleTextareaChange}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? "Listening…" : "Message Nerve net Assistant..."}
          disabled={isStreaming}
          className="flex-1 max-h-48 py-2.5 px-2 bg-transparent dark:text-white text-gray-800 placeholder-muted-foreground/60 text-sm focus:outline-none resize-none overflow-y-auto leading-relaxed"
        />

        {/* Action Controls */}
        <div className="flex items-center gap-1">
          {!micUnavailable && (
            <button
              onClick={toggleMic}
              disabled={isStreaming}
              className={`p-2.5 rounded-xl transition-all disabled:opacity-40 ${isListening
                  ? "text-red-500 bg-red-500/15 hover:bg-red-500/25"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/45"
                }`}
              title={isListening ? "Stop voice input" : "Voice input"}
            >
              {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
          )}

          {isStreaming ? (
            <button
              onClick={onStop}
              className="p-2.5 bg-red-500 hover:bg-red-600 text-white rounded-xl shadow-lg active:scale-[0.98] transition-all"
              title="Stop generating"
            >
              <Square className="w-5 h-5 fill-white" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!prompt.trim() && attachments.length === 0}
              className="p-2.5 bg-primary hover:bg-primary/95 text-white rounded-xl shadow-[0_4px_12px_rgba(139,92,246,0.2)] active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none transition-all"
              title="Send prompt"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      <div className="text-[10px] text-center text-muted-foreground/60 font-semibold mt-2 tracking-wide uppercase select-none">
        Nervenet AI can make mistakes. Consider checking important information.
      </div>
    </div>
  );
};
