import React, { useState, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { useAuth } from "@/hooks/useAuth";
import { Plus, Search, MessageSquare, Pin, Archive, Trash2, Edit2, Check, X, Settings, LogOut, LayoutDashboard, Sun, Moon } from "lucide-react";
import { Link } from "react-router-dom";
import logo from "@/assets/logo.png";
import logoLight from "@/assets/logo_light.png";

interface SidebarProps {
  onOpenSettings: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenSettings }) => {
  const {
    conversations,
    currentConversationId,
    fetchConversations,
    selectConversation,
    createConversation,
    renameConversation,
    deleteConversation,
    togglePinConversation,
    toggleArchiveConversation
  } = useChat();

  const { user, logout } = useAuth();
  
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  // Light/Dark Theme Switching
  const [theme, setTheme] = useState<"light" | "dark">(
    (localStorage.getItem("theme") as "light" | "dark") || "dark"
  );

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    window.dispatchEvent(new CustomEvent("theme-changed", { detail: nextTheme }));
  };

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleCreate = async () => {
    await createConversation("New Chat");
  };

  const handleStartEdit = (id: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(id);
    setEditTitle(currentTitle);
  };

  const handleSaveEdit = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      await renameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const filteredConversations = conversations.filter(c => 
    c.title.toLowerCase().includes(search.toLowerCase()) && !c.is_archived
  );

  return (
    <aside className="w-80 h-screen flex flex-col dark:bg-[#0f172a] bg-white border-r border-border/40 select-none text-foreground">
      {/* Brand Header */}
      <div className="p-4 pb-1 pt-5 flex items-center gap-3 select-none">
        <img src={theme === "dark" ? logo : logoLight} alt="Bharat Smart Services Logo" className="h-7 w-auto object-contain" />
        <div className="flex flex-col">
          <span className="text-xs font-black dark:text-white text-gray-800 tracking-wider uppercase">Nervenet AI</span>
          <span className="text-[9px] text-muted-foreground/60 font-bold uppercase tracking-widest">Enterprise</span>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-4">
        <button
          onClick={handleCreate}
          className="w-full flex items-center justify-center gap-2 py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-xl transition-all duration-200 shadow-[0_4px_12px_rgba(139,92,246,0.15)] active:scale-[0.98]"
        >
          <Plus className="w-5 h-5" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="px-4 mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-9 pr-4 py-2 bg-secondary/10 dark:bg-stone-900/40 border border-border/50 rounded-xl text-sm dark:text-white text-gray-800 placeholder-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 transition-all"
          />
        </div>
      </div>

      {/* Chat History List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {filteredConversations.length === 0 ? (
          <div className="text-center text-muted-foreground/50 text-xs py-8 font-medium">
            No conversations found
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = conv.id === currentConversationId;
            const isEditing = conv.id === editingId;

            return (
              <div
                key={conv.id}
                onClick={() => !isEditing && selectConversation(conv.id)}
                className={`group w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl cursor-pointer text-sm font-medium transition-all border ${
                  isActive
                    ? "bg-primary/10 dark:bg-primary/15 border-primary/30 text-primary border-l-4"
                    : "bg-muted/40 dark:bg-muted/15 border-border/20 text-muted-foreground hover:bg-muted/80 dark:hover:bg-muted/30 hover:text-foreground"
                }`}
              >
                <div className="flex items-center gap-2.5 flex-1 min-w-0">
                  <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? "text-primary" : "text-muted-foreground/75"}`} />
                  
                  {isEditing ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full bg-secondary/20 dark:bg-stone-900/60 border border-primary/50 rounded px-1.5 py-0.5 text-xs dark:text-white text-gray-800 focus:outline-none focus:ring-1 focus:ring-primary"
                      autoFocus
                    />
                  ) : (
                    <span className="truncate pr-1 text-left">{conv.title}</span>
                  )}
                </div>

                {/* Operations Toolbar */}
                <div className="hidden group-hover:flex items-center gap-1 shrink-0">
                  {isEditing ? (
                    <>
                      <button onClick={(e) => handleSaveEdit(conv.id, e)} className="p-1 hover:text-green-500 transition-colors">
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={handleCancelEdit} className="p-1 hover:text-red-500 transition-colors">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          togglePinConversation(conv.id, !conv.is_pinned);
                        }}
                        className={`p-1 hover:text-white transition-colors ${conv.is_pinned ? "text-primary hover:text-primary/80" : "text-muted-foreground/60"}`}
                        title={conv.is_pinned ? "Unpin chat" : "Pin chat"}
                      >
                        <Pin className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleStartEdit(conv.id, conv.title, e)}
                        className="p-1 text-muted-foreground/60 hover:text-white transition-colors"
                        title="Rename"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleArchiveConversation(conv.id, true);
                        }}
                        className="p-1 text-muted-foreground/60 hover:text-white transition-colors"
                        title="Archive"
                      >
                        <Archive className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                        className="p-1 text-muted-foreground/60 hover:text-red-500 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>
                
                {/* Pin indicator when not hovered */}
                {!isEditing && conv.is_pinned && (
                  <Pin className="w-3 h-3 text-primary shrink-0 group-hover:hidden" />
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Profile Section */}
      <div className="p-4 border-t border-border/40 bg-muted/30 flex flex-col gap-2">
        {user?.is_admin && (
          <Link
            to="/admin"
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-muted-foreground hover:bg-secondary/40 hover:text-white dark:hover:text-white hover:text-gray-900 transition-all"
          >
            <LayoutDashboard className="w-4 h-4 text-primary" />
            <span>Admin Dashboard</span>
          </Link>
        )}

        <div className="flex items-center justify-between gap-3 px-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center font-bold">
              {user?.full_name?.charAt(0) || user?.email.charAt(0).toUpperCase()}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-semibold dark:text-white text-gray-800 truncate">{user?.full_name || "Account"}</span>
              <span className="text-xs text-muted-foreground truncate">{user?.email}</span>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={toggleTheme}
              className="p-2 hover:bg-secondary/45 text-muted-foreground hover:text-white dark:hover:text-white hover:text-gray-900 rounded-xl transition-all"
              title="Toggle Theme"
            >
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button
              onClick={onOpenSettings}
              className="p-2 hover:bg-secondary/45 text-muted-foreground hover:text-white dark:hover:text-white hover:text-gray-900 rounded-xl transition-all"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
            <button
              onClick={logout}
              className="p-2 hover:bg-secondary/45 text-muted-foreground hover:text-red-500 rounded-xl transition-all"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
};
