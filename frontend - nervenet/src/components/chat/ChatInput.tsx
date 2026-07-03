import React, { useRef, useState } from "react";
import { Paperclip, Send, Square, X, Mic } from "lucide-react";
import { useChat } from "@/hooks/useChat";

interface ChatInputProps {
  onSend: (prompt: string, attachmentIds: string[]) => void;
  onStop: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, onStop }) => {
  const { isStreaming, uploadAttachment } = useChat();
  const [prompt, setPrompt] = useState("");
  const [attachments, setAttachments] = useState<{ id: string; name: string }[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    
    const fileId = await uploadAttachment(targetFile);
    if (fileId) {
      setAttachments((prev) => [...prev, { id: fileId, name: targetFile.name }]);
    }
    setUploading(false);
    
    // Clear input value
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

    const attachmentIds = attachments.map((a) => a.id);
    onSend(prompt, attachmentIds);
    setPrompt("");
    setAttachments([]);
    
    // Reset height of textarea
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

      {/* Input container */}
      <div className="relative flex items-end gap-2 p-2 bg-secondary/35 border border-border/60 rounded-2xl focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary/45 transition-all">
        {/* Attachment upload trigger */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          className="hidden"
          accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.xls,image/*"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || isStreaming}
          className="p-2.5 hover:bg-secondary/45 text-muted-foreground hover:text-foreground rounded-xl transition-all disabled:opacity-40"
          title="Attach file"
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
          placeholder="Message Nerve net Assistant..."
          disabled={isStreaming}
          className="flex-1 max-h-48 py-2.5 px-2 bg-transparent dark:text-white text-gray-800 placeholder-muted-foreground/60 text-sm focus:outline-none resize-none overflow-y-auto leading-relaxed"
        />

        {/* Action Controls */}
        <div className="flex items-center gap-1">
          <button
            className="p-2.5 text-muted-foreground hover:text-foreground rounded-xl hover:bg-secondary/45 transition-all"
            title="Voice input"
          >
            <Mic className="w-5 h-5" />
          </button>
          
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
        Cloud AI can make mistakes. Consider checking important information.
      </div>
    </div>
  );
};
