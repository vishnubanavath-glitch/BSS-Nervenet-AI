import { create } from "zustand";
import api from "@/lib/api";

export interface Conversation {
  id: string;
  title: string;
  is_archived: boolean;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  extracted_text?: string;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata?: any;
  created_at: string;
  attachments?: Attachment[];
}

export interface Model {
  model_id: string;
  display_name: string;
  provider: string;
  context_window: number;
}

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  models: Model[];
  selectedModelId: string;
  selectedProvider: string;
  isStreaming: boolean;
  loading: boolean;
  activeArtifact: { title: string; code: string; language: string; messageId: string } | null;
  
  fetchConversations: () => Promise<void>;
  fetchMessages: (id: string) => Promise<void>;
  fetchModels: () => Promise<void>;
  selectConversation: (id: string | null) => void;
  createConversation: (title?: string) => Promise<Conversation>;
  renameConversation: (id: string, title: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  togglePinConversation: (id: string, isPinned: boolean) => Promise<void>;
  toggleArchiveConversation: (id: string, isArchived: boolean) => Promise<void>;
  setSelectedModel: (modelId: string, provider: string) => void;
  setStreaming: (streaming: boolean) => void;
  addMessage: (msg: Message) => void;
  updateAssistantMessage: (msgId: string, token: string) => void;
  finalizeAssistantMessage: (msgId: string, fullContent: string, telemetry?: any) => void;
  setActiveArtifact: (artifact: { title: string; code: string; language: string; messageId: string } | null) => void;
  clearStore: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  messages: [],
  models: [],
  selectedModelId: "gpt-4o",
  selectedProvider: "openai",
  isStreaming: false,
  loading: false,
  activeArtifact: null,

  fetchConversations: async () => {
    set({ loading: true });
    try {
      const res = await api.get("/conversations");
      set({ conversations: res.data, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchMessages: async (id) => {
    set({ loading: true });
    try {
      const res = await api.get(`/conversations/${id}/messages`);
      set({ messages: res.data, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  fetchModels: async () => {
    try {
      const res = await api.get("/models");
      const models = res.data;
      set({ models });
      if (models.length > 0) {
        // Default to Claude Sonnet 4.6; fall back to first model if not available
        const preferred = models.find((m: { model_id: string }) => m.model_id === "claude-sonnet-4-6");
        const defaultModel = preferred ?? models[0];
        set({ selectedModelId: defaultModel.model_id, selectedProvider: defaultModel.provider });
      }
    } catch (err) {
      console.error("Failed to load models:", err);
    }
  },

  selectConversation: (id) => {
    set({ currentConversationId: id, messages: [] });
    if (id) {
      get().fetchMessages(id);
    }
  },

  createConversation: async (title = "New Chat") => {
    const res = await api.post("/conversations", { title });
    const conv = res.data;
    set((state) => {
      const exists = state.conversations.some((c) => c.id === conv.id);
      return {
        conversations: exists ? state.conversations : [conv, ...state.conversations],
        currentConversationId: conv.id,
        messages: []
      };
    });
    return conv;
  },

  renameConversation: async (id, title) => {
    await api.put(`/conversations/${id}`, { title });
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }));
  },

  deleteConversation: async (id) => {
    await api.delete(`/conversations/${id}`);
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      currentConversationId: state.currentConversationId === id ? null : state.currentConversationId,
      messages: state.currentConversationId === id ? [] : state.messages
    }));
  },

  togglePinConversation: async (id, isPinned) => {
    await api.put(`/conversations/${id}`, { is_pinned: isPinned });
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, is_pinned: isPinned } : c
      ).sort((a, b) => {
        if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      })
    }));
  },

  toggleArchiveConversation: async (id, isArchived) => {
    await api.put(`/conversations/${id}`, { is_archived: isArchived });
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      currentConversationId: state.currentConversationId === id ? null : state.currentConversationId,
      messages: state.currentConversationId === id ? [] : state.messages
    }));
  },

  setSelectedModel: (modelId, provider) => {
    set({ selectedModelId: modelId, selectedProvider: provider });
  },

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  addMessage: (msg) => {
    set((state) => ({ messages: [...state.messages, msg] }));
  },

  updateAssistantMessage: (msgId, token) => {
    set((state) => {
      const existingMsg = state.messages.find((m) => m.id === msgId);
      if (existingMsg) {
        return {
          messages: state.messages.map((m) =>
            m.id === msgId ? { ...m, content: m.content + token } : m
          ),
        };
      } else {
        // Initial token chunk, create assistant message placeholder
        const newMsg: Message = {
          id: msgId,
          conversation_id: state.currentConversationId || "",
          role: "assistant",
          content: token,
          created_at: new Date().toISOString(),
        };
        return { messages: [...state.messages, newMsg] };
      }
    });
  },

  finalizeAssistantMessage: (msgId, fullContent, telemetry) => {
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === msgId ? { ...m, content: fullContent, metadata: { ...m.metadata, telemetry } } : m
      ),
      isStreaming: false
    }));
  },

  setActiveArtifact: (artifact) => set({ activeArtifact: artifact }),
  clearStore: () => set({
    conversations: [],
    currentConversationId: null,
    messages: [],
    activeArtifact: null
  })
}));
