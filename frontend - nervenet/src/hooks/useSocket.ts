import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "@/store/authStore";
import { useChatStore } from "@/store/chatStore";

export const useSocket = () => {
  const socketRef = useRef<WebSocket | null>(null);
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
        } else if (evType === "stopped") {
          setStreaming(false);
        }
      } catch (err) {
        console.error("Parsing message failed:", err);
      }
    };

    socket.onclose = () => {
      console.log("WebSocket stream disconnected");
    };

    socket.onerror = (error) => {
      console.error("WebSocket socket error:", error);
      setStreaming(false);
    };

    socketRef.current = socket;
  }, [accessToken, selectedModelId, selectedProvider, setStreaming, updateAssistantMessage, finalizeAssistantMessage, addMessage]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((prompt: string, attachmentIds: string[] = [], convId?: string, memoryUpdates?: Record<string, any>) => {
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
      attachments: [] // Attachments list can be synced after REST attachment fetches
    });

    setStreaming(true);

    const payload = {
      action: "message",
      conversation_id: activeConvId,
      prompt,
      provider: selectedProvider,
      model: selectedModelId,
      attachment_ids: attachmentIds,
      memory_updates: memoryUpdates
    };

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
