import { useCallback } from "react";
import { useChatStore } from "@/store/chatStore";
import api from "@/lib/api";

export const useChat = () => {
  const {
    conversations,
    currentConversationId,
    messages,
    models,
    selectedModelId,
    selectedProvider,
    isStreaming,
    loading,
    fetchConversations,
    fetchMessages,
    fetchModels,
    selectConversation,
    createConversation,
    renameConversation,
    deleteConversation,
    togglePinConversation,
    toggleArchiveConversation,
    setSelectedModel,
    setStreaming,
    activeArtifact,
    setActiveArtifact
  } = useChatStore();

  const uploadAttachment = useCallback(async (file: File): Promise<string | null> => {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/files/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      return res.data.id;
    } catch (err) {
      console.error("Upload attachment failed:", err);
      return null;
    }
  }, []);

  return {
    conversations,
    currentConversationId,
    messages,
    models,
    selectedModelId,
    selectedProvider,
    isStreaming,
    loading,
    fetchConversations,
    fetchMessages,
    fetchModels,
    selectConversation,
    createConversation,
    renameConversation,
    deleteConversation,
    togglePinConversation,
    toggleArchiveConversation,
    setSelectedModel,
    setStreaming,
    uploadAttachment,
    activeArtifact,
    setActiveArtifact
  };
};
