import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "@/store/authStore";
import { useChatStore } from "@/store/chatStore";

export const useSocket = () => {
  const socketRef = useRef<WebSocket | null>(null);
  const streamingWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { accessToken } = useAuthStore();
  const {
    selectedModelId,
    selectedProvider,
    setStreaming,
    updateAssistantMessage,
    finalizeAssistantMessage,
    addMessage
  } = useChatStore();

  const connect = useCallback(() => {
    if (!accessToken) return;
    
    // Check if socket is already open or opening
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsUrl = (import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/ws/chat") + `?token=${accessToken}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("WebSocket stream connected");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const { event: evType, conversation_id, token, message_id, content, telemetry, error } = data;
        const activeConvId = useChatStore.getState().currentConversationId;

        if (error) {
          console.error("Socket chat error:", error);
          addMessage({
            id: crypto.randomUUID(),
            conversation_id: conversation_id || activeConvId,
            role: "assistant",
            content: `⚠️ **API Error:** ${error}`,
            created_at: new Date().toISOString()
          });
          setStreaming(false);
          if (streamingWatchdogRef.current) clearTimeout(streamingWatchdogRef.current);
          return;
        }

        if (conversation_id !== activeConvId) return;

        if (evType === "token") {
          updateAssistantMessage(message_id, token);
        } else if (evType === "done") {
          finalizeAssistantMessage(message_id, content, telemetry);
          if (data.title) {
            useChatStore.setState((state) => ({
              conversations: state.conversations.map((c) =>
                c.id === conversation_id ? { ...c, title: data.title } : c
              )
            }));
          }
          setStreaming(false);
          if (streamingWatchdogRef.current) clearTimeout(streamingWatchdogRef.current);
        } else if (evType === "title_update") {
          // Title was generated in the background after the main response
          // Update the sidebar conversation title now that it's ready
          useChatStore.setState((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === conversation_id ? { ...c, title: data.title } : c
            )
          }));
        } else if (evType === "stopped") {
          setStreaming(false);
        }
      } catch (err) {
        console.error("Parsing message failed:", err);
      }
    };

    socket.onclose = () => {
      console.log("WebSocket stream disconnected");
      // Always clear streaming state when socket drops — prevents permanent lock
      setStreaming(false);
      if (streamingWatchdogRef.current) clearTimeout(streamingWatchdogRef.current);
    };

    socket.onerror = (error) => {
      console.error("WebSocket socket error:", error);
      setStreaming(false);
      if (streamingWatchdogRef.current) clearTimeout(streamingWatchdogRef.current);
    };

    socketRef.current = socket;
  }, [accessToken, selectedModelId, selectedProvider, setStreaming, updateAssistantMessage, finalizeAssistantMessage, addMessage]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((prompt: string, attachments: any[] = [], convId?: string, memoryUpdates?: Record<string, any>) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      console.error("Cannot send message: socket is not open. Reconnecting...");
      connect();
      return false;
    }

    const activeConvId = convId || useChatStore.getState().currentConversationId;
    if (!activeConvId) return false;

    // Immediately push user message into chat UI for immediate response feel
    const tempUserMsgId = crypto.randomUUID();
    addMessage({
      id: tempUserMsgId,
      conversation_id: activeConvId,
      role: "user",
      content: prompt,
      created_at: new Date().toISOString(),
      attachments: attachments.map(a => ({
        id: a.id,
        filename: a.filename || a.name || "Attachment",
        mime_type: a.mime_type || "application/octet-stream",
        file_size: a.file_size || 0,
        created_at: new Date().toISOString()
      }))
    });

    setStreaming(true);

    // Safety watchdog: if no 'done' or 'stopped' event arrives within 90s,
    // force-clear streaming so Enter key is never permanently locked.
    if (streamingWatchdogRef.current) clearTimeout(streamingWatchdogRef.current);
    streamingWatchdogRef.current = setTimeout(() => {
      console.warn("Streaming watchdog fired — force-clearing stuck streaming state");
      setStreaming(false);
    }, 90000);

    const attachmentIds = attachments.map(a => a.id);
    const payload = {
      action: "message",
      conversation_id: activeConvId,
      prompt,
      provider: selectedProvider,
      model: selectedModelId,
      attachment_ids: attachmentIds,
      memory_updates: memoryUpdates
    };

    console.log("WebSocket sending message payload:", payload);
    socketRef.current.send(json_stringify(payload));
    return true;
  }, [selectedModelId, selectedProvider, addMessage, setStreaming, connect]);

  const stopGeneration = useCallback(() => {
    const activeConvId = useChatStore.getState().currentConversationId;
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN || !activeConvId) {
      return;
    }

    const payload = {
      action: "stop",
      conversation_id: activeConvId
    };
    socketRef.current.send(json_stringify(payload));
    setStreaming(false);
  }, [setStreaming]);

  // Auto connect when credentials are hot
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    sendMessage,
    stopGeneration,
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
};

// Helper function because of JSON stringify imports
function json_stringify(obj: any): string {
  return JSON.stringify(obj);
}
