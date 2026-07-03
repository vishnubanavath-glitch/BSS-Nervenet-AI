import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import {
  ArrowLeft, Users, TrendingUp, Cpu,
  Settings, Key, Layers, ShieldCheck, Database, CreditCard,
  Plus, X, RefreshCw, HelpCircle, Eye, EyeOff
} from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export const Admin: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState<any>(null);

  // States for different management sections
  const [users, setUsers] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [providers, setProviders] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [files, setFiles] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [tickets, setTickets] = useState<any[]>([]);
  const [settings, setSettings] = useState<any[]>([]);
  // Real quota data per provider: { [providerId]: quotaData | "loading" | "error" }
  const [quotaMap, setQuotaMap] = useState<Record<string, any>>({});
  
  // MCP states
  const [mcpServers, setMcpServers] = useState<any[]>([]);
  const [mcpTestStatus, setMcpTestStatus] = useState<Record<string, any>>({});
  const [showAddMcp, setShowAddMcp] = useState(false);
  const [newMcp, setNewMcp] = useState({
    name: "",
    description: "",
    server_type: "sse",
    url: "",
    command: "",
    env_variables: ""
  });
  const [editingMcpId, setEditingMcpId] = useState<string | null>(null);
  const [editingMcpData, setEditingMcpData] = useState({
    name: "",
    description: "",
    server_type: "sse",
    url: "",
    command: "",
    env_variables: ""
  });

  // Selection states & modals
  const [showKeyMap, setShowKeyMap] = useState<Record<string, boolean>>({});
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [creditsToGrant, setCreditsToGrant] = useState<number>(10);
  const [showCreditsModal, setShowCreditsModal] = useState(false);
  const [newPlan, setNewPlan] = useState({ name: "", price: 0, tokens: 100000, msgs: 1000, upload: 10 });
  const [newModel, setNewModel] = useState({ provider: "claude", id: "", name: "", context: 100000 });

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [
        resDash, resUsers, resProv, resModels, resPlans, resFiles, resLogs, resTickets, resSettings, resMcp
      ] = await Promise.all([
        api.get("/admin/dashboard"),
        api.get("/admin/users"),
        api.get("/admin/providers"),
        api.get("/admin/models"),
        api.get("/admin/subscriptions"),
        api.get("/admin/files"),
        api.get("/admin/logs"),
        api.get("/admin/tickets"),
        api.get("/admin/settings"),
        api.get("/admin/mcp")
      ]);
      setDashboardData(resDash.data);
      setUsers(resUsers.data);
      setProviders(resProv.data);
      setModels(resModels.data);
      setMcpServers(resMcp.data || []);
      // Also fetch platform wallet balance to calculate token capacity
      try {
        await api.get("/payment/balance");
      } catch {}
      setPlans(resPlans.data);
      setFiles(resFiles.data);
      setAuditLogs(resLogs.data);
      setTickets(resTickets.data);
      setSettings(resSettings.data);
    } catch (err) {
      console.error("Admin dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleUserBan = async (userId: string) => {
    try {
      await api.post(`/admin/users/${userId}/ban`);
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: !u.is_active } : u));
    } catch (err) {
      console.error(err);
    }
  };

  const handleGrantCredits = async () => {
    if (!selectedUser) return;
    try {
      await api.post(`/admin/users/${selectedUser.id}/credits`, { credits_amount: creditsToGrant });
      alert(`Granted ${creditsToGrant} credits successfully!`);
      setShowCreditsModal(false);
      fetchDashboardData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!confirm("Are you sure you want to delete this user?")) return;
    try {
      await api.delete(`/admin/users/${userId}`);
      setUsers(prev => prev.filter(u => u.id !== userId));
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleProvider = async (providerId: string, isEnabled: boolean) => {
    try {
      await api.put(`/admin/providers/${providerId}`, { is_enabled: !isEnabled });
      setProviders(prev => prev.map(p => p.id === providerId ? { ...p, is_enabled: !isEnabled } : p));
      alert(`Provider status updated successfully! Now ${!isEnabled ? "ENABLED" : "DISABLED"}.`);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateProviderKey = async (providerId: string, key: string) => {
    try {
      const res = await api.put(`/admin/providers/${providerId}`, { api_key: key });
      setProviders(prev => prev.map(p => p.id === providerId ? res.data : p));
      // Clear old quota when key changes
      setQuotaMap(prev => { const n = {...prev}; delete n[providerId]; return n; });
      if (key === "") {
        alert("API Key removed successfully!");
      } else {
        if (res.data.health_status === "healthy") {
          alert("🎉 API Key verified successfully! Connection status: SYNCED & CONNECTED.");
        } else if (res.data.health_status === "unauthorized") {
          alert("❌ API Key saved, but connection verification FAILED: Invalid API Key / Unauthorized.");
        } else {
          alert("⚠️ API Key saved, but connection verification returned an error. Please verify network access.");
        }
      }
      fetchDashboardData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleCheckQuota = async (providerId: string) => {
    setQuotaMap(prev => ({ ...prev, [providerId]: "loading" }));
    try {
      const res = await api.get(`/admin/providers/${providerId}/quota`);
      setQuotaMap(prev => ({ ...prev, [providerId]: res.data }));
    } catch (err: any) {
      setQuotaMap(prev => ({
        ...prev,
        [providerId]: { error: err?.response?.data?.detail || "Failed to fetch quota" }
      }));
    }
  };

  const handleAddMcpServer = async () => {
    try {
      if (!newMcp.name.trim()) return alert("Please specify a name");
      if (newMcp.server_type === "sse" && !newMcp.url.trim()) return alert("Please specify a URL");
      if (newMcp.server_type === "command" && !newMcp.command.trim()) return alert("Please specify a shell command");

      await api.post("/admin/mcp", {
        name: newMcp.name,
        description: newMcp.description,
        server_type: newMcp.server_type,
        url: newMcp.url,
        command: newMcp.command,
        env_variables: newMcp.env_variables ? newMcp.env_variables : null
      });
      
      alert("MCP Server registered successfully!");
      setShowAddMcp(false);
      setNewMcp({ name: "", description: "", server_type: "sse", url: "", command: "", env_variables: "" });
      fetchDashboardData();
    } catch (e: any) {
      alert("Failed to add MCP server: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleToggleMcpServer = async (id: string, currentlyEnabled: boolean) => {
    try {
      await api.put(`/admin/mcp/${id}`, { is_enabled: !currentlyEnabled });
      fetchDashboardData();
    } catch (e: any) {
      alert("Failed to toggle MCP server: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleDeleteMcpServer = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this MCP server? This will remove all its tools from the chat assistant.")) return;
    try {
      await api.delete(`/admin/mcp/${id}`);
      alert("MCP server deleted.");
      fetchDashboardData();
    } catch (e: any) {
      alert("Failed to delete MCP server: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleSaveMcpEdit = async (id: string) => {
    try {
      if (!editingMcpData.name.trim()) return alert("Name is required");
      if (editingMcpData.server_type === "sse" && !editingMcpData.url.trim()) return alert("URL is required");
      if (editingMcpData.server_type === "command" && !editingMcpData.command.trim()) return alert("Shell command is required");

      await api.put(`/admin/mcp/${id}`, {
        name: editingMcpData.name,
        description: editingMcpData.description,
        server_type: editingMcpData.server_type,
        url: editingMcpData.url,
        command: editingMcpData.command,
        env_variables: editingMcpData.env_variables ? editingMcpData.env_variables : ""
      });

      alert("MCP Server updated successfully!");
      setEditingMcpId(null);
      fetchDashboardData();
    } catch (e: any) {
      alert("Failed to update MCP server: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleTestMcpServer = async (id: string) => {
    setMcpTestStatus(prev => ({ ...prev, [id]: { status: "loading" } }));
    try {
      const res = await api.post(`/admin/mcp/${id}/test`);
      setMcpTestStatus(prev => ({ ...prev, [id]: res.data }));
    } catch (e: any) {
      setMcpTestStatus(prev => ({ ...prev, [id]: { status: "error", detail: e?.response?.data?.detail || e.message } }));
    }
  };

  const handleAddPlan = async () => {
    try {
      await api.post("/admin/subscriptions", {
        name: newPlan.name,
        monthly_price: newPlan.price,
        monthly_token_limit: newPlan.tokens,
        monthly_message_limit: newPlan.msgs,
        max_upload_size_mb: newPlan.upload
      });
      alert("Billing plan created!");
      fetchDashboardData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddModel = async () => {
    try {
      await api.post("/admin/models", {
        provider_name: newModel.provider,
        model_id: newModel.id,
        display_name: newModel.name,
        context_window: newModel.context,
        is_active: true
      });
      alert("Model registered!");
      fetchDashboardData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleResolveTicket = async (ticketId: string, notes: string) => {
    try {
      await api.put(`/admin/tickets/${ticketId}`, { status: "resolved", internal_notes: notes });
      alert("Ticket status resolved!");
      fetchDashboardData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateSetting = async (key: string, value: string) => {
    try {
      await api.put(`/admin/settings?key=${key}`, { setting_value: value });
      alert("Setting updated successfully!");
      fetchDashboardData();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#060608] text-foreground">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          <span className="text-sm font-semibold text-muted-foreground">Loading admin operations panel...</span>
        </div>
      </div>
    );
  }

  const filteredUsers = users.filter(
    u => u.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
         u.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#070709] text-gray-200 flex">
      {/* ── SIDEBAR ────────────────────────────────────────────── */}
      <aside className="w-64 bg-[#0a0a0d] border-r border-border/40 flex flex-col shrink-0">
        <div className="p-6 border-b border-border/30 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-lg shadow-inner">
            🛡️
          </div>
          <div>
            <h2 className="text-xs font-bold text-white uppercase tracking-wider">Platform Control</h2>
            <span className="text-[10px] text-muted-foreground font-semibold uppercase">Super Admin Portal</span>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
          {[
            { id: "dashboard", label: "Dashboard Overview", icon: TrendingUp },
            { id: "users", label: "Users & Accounts", icon: Users },
            { id: "providers", label: "API Keys & Providers", icon: Key },
            { id: "models", label: "Model Configuration", icon: Layers },
            { id: "mcp", label: "MCP Tools / Servers", icon: Cpu },
            { id: "billing", label: "Subscription Plans", icon: CreditCard },
            { id: "files", label: "Storage & Files", icon: Database },
            { id: "tickets", label: "Support Desk", icon: HelpCircle },
            { id: "settings", label: "System Settings", icon: Settings },
            { id: "logs", label: "Audit & Security Logs", icon: ShieldCheck }
          ].map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-xs font-bold rounded-xl transition-all ${
                  activeTab === item.id
                    ? "bg-primary text-white shadow-lg shadow-primary/10 border border-primary/20"
                    : "text-muted-foreground hover:text-white hover:bg-secondary/20"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border/30 select-none">
          <Link
            to="/"
            className="flex items-center justify-center gap-2 py-2.5 bg-secondary/30 hover:bg-secondary/50 border border-border rounded-xl text-xs font-bold text-white transition-all active:scale-[0.98]"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Chat</span>
          </Link>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ─────────────────────────────────────── */}
      <main className="flex-1 h-screen overflow-y-auto p-8 relative">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Control
            </h1>
            <p className="text-muted-foreground text-xs font-medium mt-1">
              Admin console telemetry & operations dashboard
            </p>
          </div>
          <button
            onClick={fetchDashboardData}
            className="flex items-center gap-2 px-3 py-2 bg-secondary/35 border border-border rounded-xl hover:bg-secondary/50 hover:text-white text-xs font-bold transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </header>

        {/* ── TAB CONTENT: DASHBOARD OVERVIEW ────────────────────── */}
        {activeTab === "dashboard" && (
          <div className="space-y-8 animate-in fade-in duration-200">
            {/* Quick Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {[
                { label: "Total Accounts", val: dashboardData?.total_users || 0, icon: Users, desc: "Banned or active" },
                { label: "New Today", val: dashboardData?.new_users_today || 0, icon: Plus, desc: "User registrations today" },
                { label: "Revenue generated", val: `$${dashboardData?.estimated_revenue?.toFixed(2) || 0.0}`, icon: CreditCard, desc: "Paid invoices" },
                { label: "Active Subscriptions", val: dashboardData?.active_subscriptions || 0, icon: ShieldCheck, desc: "Pro & Enterprise tiers" }
              ].map((c, idx) => {
                const Icon = c.icon;
                return (
                  <div key={idx} className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl flex items-center justify-between">
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{c.label}</span>
                      <div className="text-2xl font-extrabold text-white">{c.val}</div>
                      <span className="text-[10px] text-muted-foreground/60 block font-medium">{c.desc}</span>
                    </div>
                    <div className="w-11 h-11 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-inner">
                      <Icon className="w-5 h-5" />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Charts View */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-6">Token Costs History (7 Days)</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={dashboardData?.daily_usage || []}>
                      <defs>
                        <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                      <XAxis dataKey="date" stroke="#666" fontSize={10} />
                      <YAxis stroke="#666" fontSize={10} />
                      <Tooltip contentStyle={{ backgroundColor: "#0c0c0e", borderColor: "#333", color: "#fff" }} />
                      <Area type="monotone" dataKey="cost" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorCost)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Provider Performance Health Panel */}
              <div className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl space-y-4">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">Provider Service Status</h3>
                <div className="space-y-3.5">
                  {providers.map(p => (
                    <div key={p.id} className="p-3 bg-secondary/10 border border-border/30 rounded-xl flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{p.is_enabled ? "🟢" : "🔴"}</span>
                        <div className="flex flex-col">
                          <span className="text-xs font-bold text-white uppercase tracking-tight">{p.provider_name}</span>
                          <span className="text-[9px] text-muted-foreground">Requests: {p.request_count}</span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] font-bold text-muted-foreground">{p.avg_latency_ms.toFixed(0)} ms</span>
                        <span className="text-[9px] text-red-400 font-semibold">{p.error_count} Errors</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB CONTENT: USERS DIRECTORY ───────────────────────── */}
        {activeTab === "users" && (
          <div className="space-y-6 animate-in fade-in duration-200">
            {/* Search filter banner */}
            <div className="p-4 bg-[#0a0a0d] border border-border/40 rounded-2xl flex items-center justify-between">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search user email or display name..."
                className="bg-secondary/15 border border-border/60 hover:border-primary/20 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 w-80 text-white outline-none transition-all"
              />
            </div>

            {/* Users Directory Table */}
            <div className="bg-[#0a0a0d] border border-border/40 rounded-2xl overflow-hidden shadow-2xl">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border/60">
                  <thead className="bg-[#060608]">
                    <tr>
                      <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Account Identity</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Prepaid Balance</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Tokens Consumed</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Authority Status</th>
                      <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Ban Policy</th>
                      <th className="px-6 py-3.5 text-right text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Operations</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50 bg-[#0a0a0d]/20">
                    {filteredUsers.map(u => (
                      <tr key={u.id}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-primary/20 text-primary border border-primary/20 flex items-center justify-center font-bold">
                              {u.full_name?.charAt(0) || "U"}
                            </div>
                            <div className="flex flex-col">
                              <span className="text-xs font-bold text-white">{u.full_name || "Guest Account"}</span>
                              <span className="text-[10px] text-muted-foreground">{u.email}</span>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs font-black text-emerald-400">
                          ${u.balance !== undefined ? u.balance.toFixed(2) : "0.00"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-violet-400/90">
                          {u.total_tokens_used !== undefined ? u.total_tokens_used.toLocaleString() : "0"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {u.is_admin ? (
                            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-primary/10 text-primary border border-primary/20 uppercase tracking-wide">
                              Admin Access
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-secondary/30 text-muted-foreground border border-border/60 uppercase tracking-wide">
                              Standard User
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wide ${
                            u.is_active ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-red-500/10 text-red-500 border border-red-500/20"
                          }`}>
                            {u.is_active ? "Whitelisted" : "Banned"}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-xs font-semibold space-x-2">
                          <button
                            onClick={() => { setSelectedUser(u); setShowCreditsModal(true); }}
                            className="px-2.5 py-1.5 bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 text-amber-500 rounded-lg font-bold text-[10px] uppercase transition-all"
                          >
                            + Credits
                          </button>
                          <button
                            onClick={() => handleToggleUserBan(u.id)}
                            className={`px-2.5 py-1.5 rounded-lg border text-[10px] font-bold uppercase transition-all ${
                              u.is_active
                                ? "bg-red-500/10 border-red-500/20 text-red-500 hover:bg-red-500/20"
                                : "bg-green-500/10 border-green-500/20 text-green-500 hover:bg-green-500/20"
                            }`}
                          >
                            {u.is_active ? "Ban" : "Unban"}
                          </button>
                          <button
                            onClick={() => handleDeleteUser(u.id)}
                            className="px-2.5 py-1.5 bg-secondary border border-border/80 text-white hover:bg-red-500/20 hover:text-red-500 rounded-lg font-bold text-[10px] uppercase transition-all"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB CONTENT: API KEYS & PROVIDERS ──────────────────── */}
        {activeTab === "providers" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in duration-200">
            {providers.map(p => {
              const isShowing = showKeyMap[p.id] || false;
              return (
                <div key={p.id} className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">
                          {p.provider_name === "claude" || p.provider_name === "anthropic" ? "🎨" : p.provider_name === "openai" ? "🌐" : "⚡"}
                        </span>
                        <div className="flex flex-col">
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider">{p.provider_name}</h3>
                          <span className={`text-[9px] font-black uppercase tracking-wider mt-0.5 ${
                            p.health_status === "healthy"
                              ? "text-emerald-400"
                              : p.health_status === "unauthorized"
                              ? "text-red-400"
                              : "text-amber-500"
                          }`}>
                            {p.health_status === "healthy" ? "🟢 Synced & Connected" : p.health_status === "unauthorized" ? "🔴 Sync Failed (Bad Key)" : "🟡 Unconfigured"}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleToggleProvider(p.id, p.is_enabled)}
                        className={`px-3 py-1.5 rounded-xl border text-[10px] font-bold uppercase transition-all ${
                          p.is_enabled
                            ? "bg-green-500/10 border-green-500/20 text-green-500 hover:bg-green-500/20"
                            : "bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20"
                        }`}
                      >
                        {p.is_enabled ? "Enabled" : "Disabled"}
                      </button>
                    </div>

                     <div className="space-y-2">
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide block">Secure API Key</label>
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <input
                            type={isShowing ? "text" : "password"}
                            placeholder={p.api_key_encrypted ? "••••••••••••••••••••••••••••••••" : "No Key Set"}
                            value={providerKeys[p.id] || ""}
                            onChange={e => setProviderKeys(prev => ({ ...prev, [p.id]: e.target.value }))}
                            className="w-full bg-[#08080a] border border-border/70 focus:border-primary/50 text-xs font-mono rounded-xl pl-4 pr-10 py-2.5 text-white outline-none"
                          />
                          <button
                            type="button"
                            onClick={() => setShowKeyMap(prev => ({ ...prev, [p.id]: !isShowing }))}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white"
                          >
                            {isShowing ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                        <button
                          onClick={() => {
                            const val = providerKeys[p.id];
                            if (!val || !val.trim()) {
                              alert("Please type a key value first to save.");
                              return;
                            }
                            handleUpdateProviderKey(p.id, val.trim());
                            setProviderKeys(prev => ({ ...prev, [p.id]: "" }));
                          }}
                          className="px-4 py-2 bg-primary hover:bg-primary/95 text-white text-xs font-bold rounded-xl whitespace-nowrap select-none transition-all active:scale-95"
                        >
                          Save Key
                        </button>
                        {p.api_key_encrypted && (
                          <button
                            onClick={() => {
                              if (window.confirm("Are you sure you want to delete this provider's API key?")) {
                                handleUpdateProviderKey(p.id, "");
                              }
                            }}
                            className="px-3.5 py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 text-xs font-bold rounded-xl whitespace-nowrap select-none transition-all active:scale-95"
                          >
                            Remove Key
                          </button>
                        )}
                      </div>
                      <p className="text-[9px] text-muted-foreground/60 italic">Key will be encrypted with AES-256-GCM before storage</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 border-t border-border/25 pt-4 mt-6">
                    <div className="text-center">
                      <span className="text-[9px] text-muted-foreground uppercase font-bold block">Latency</span>
                      <span className="text-xs font-bold text-white">{p.avg_latency_ms.toFixed(0)} ms</span>
                    </div>
                    <div className="text-center border-x border-border/25">
                      <span className="text-[9px] text-muted-foreground uppercase font-bold block">Requests</span>
                      <span className="text-xs font-bold text-white">{p.request_count}</span>
                    </div>
                    <div className="text-center">
                      <span className="text-[9px] text-red-400 uppercase font-bold block">Errors</span>
                      <span className="text-xs font-bold text-red-400">{p.error_count}</span>
                    </div>
                  </div>

                  {/* Live Provider Quota Check */}
                  {p.api_key_encrypted && (() => {
                    const qData = quotaMap[p.id];
                    return (
                      <div className="mt-4 border-t border-border/20 pt-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">API Quota Rate-Limits</span>
                          <button
                            onClick={() => handleCheckQuota(p.id)}
                            disabled={qData === "loading"}
                            className="px-2.5 py-1 bg-primary/10 hover:bg-primary/25 border border-primary/20 text-primary hover:text-white text-[9px] font-extrabold rounded-lg transition-all disabled:opacity-50 select-none active:scale-95"
                          >
                            {qData === "loading" ? "Checking..." : "Check Live Quota"}
                          </button>
                        </div>

                        {qData === "loading" && (
                          <div className="py-2.5 text-center text-[10px] text-muted-foreground font-semibold flex items-center justify-center gap-1.5 animate-pulse">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
                            Pinging {p.provider_name} API...
                          </div>
                        )}

                        {qData && qData !== "loading" && qData.error && (
                          <div className="p-2 rounded-xl bg-red-500/5 border border-red-500/10 text-red-400 text-[9px] font-bold">
                            ⚠️ {qData.error}
                          </div>
                        )}

                        {qData && qData !== "loading" && !qData.error && (
                          <div className="bg-secondary/15 rounded-xl border border-border/40 p-2.5 space-y-2 text-[10px] font-medium text-gray-300">
                            {/* Token Quota Metrics */}
                            {qData.tokens_limit !== null && (
                              <div className="flex justify-between items-center pb-1 border-b border-border/10">
                                <span className="text-muted-foreground">TPM Limit (Tokens/min):</span>
                                <span className="font-extrabold text-white">
                                  {qData.tokens_limit.toLocaleString()}
                                </span>
                              </div>
                            )}
                            {qData.tokens_remaining !== null && (
                              <div className="flex justify-between items-center pb-1 border-b border-border/10">
                                <span className="text-muted-foreground">TPM Remaining:</span>
                                <span className={`font-black ${qData.tokens_remaining < (qData.tokens_limit || 0) * 0.1 ? 'text-red-400' : 'text-emerald-400'}`}>
                                  {qData.tokens_remaining.toLocaleString()}
                                </span>
                              </div>
                            )}

                            {/* Request limits */}
                            {qData.requests_limit !== null && (
                              <div className="flex justify-between items-center pb-1 border-b border-border/10">
                                <span className="text-muted-foreground">RPM Limit (Req/min):</span>
                                <span className="font-extrabold text-white">
                                  {qData.requests_limit.toLocaleString()}
                                </span>
                              </div>
                            )}
                            {qData.requests_remaining !== null && (
                              <div className="flex justify-between items-center">
                                <span className="text-muted-foreground">RPM Remaining:</span>
                                <span className={`font-black ${qData.requests_remaining < (qData.requests_limit || 0) * 0.1 ? 'text-red-400' : 'text-emerald-400'}`}>
                                  {qData.requests_remaining.toLocaleString()}
                                </span>
                              </div>
                            )}

                            {/* Reset window */}
                            {qData.tokens_reset && (
                              <div className="text-[8px] text-muted-foreground/60 text-right pt-1 font-semibold uppercase">
                                Resets in {qData.tokens_reset}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              );
            })}
          </div>
        )}

        {/* ── TAB CONTENT: MODEL CONFIGURATION ───────────────────── */}
        {activeTab === "models" && (
          <div className="space-y-8 animate-in fade-in duration-200">
            {/* Add Model Panel */}
            <div className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl space-y-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Plus className="w-4 h-4 text-primary" /> Register New Model
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <select
                  value={newModel.provider}
                  onChange={e => setNewModel(prev => ({ ...prev, provider: e.target.value }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none transition-all"
                >
                  <option value="claude">Claude</option>
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
                  <option value="grok">Grok</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="ollama">Ollama</option>
                </select>
                <input
                  type="text"
                  placeholder="model-id (e.g. gpt-4o-mini)"
                  value={newModel.id}
                  onChange={e => setNewModel(prev => ({ ...prev, id: e.target.value }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none transition-all"
                />
                <input
                  type="text"
                  placeholder="Display name (e.g. GPT-4o Mini)"
                  value={newModel.name}
                  onChange={e => setNewModel(prev => ({ ...prev, name: e.target.value }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none transition-all"
                />
                <button
                  onClick={handleAddModel}
                  className="w-full flex items-center justify-center py-2.5 bg-primary hover:bg-primary/95 text-white font-bold rounded-xl text-xs transition-all active:scale-[0.98]"
                >
                  Register Model
                </button>
              </div>
            </div>

            {/* Models Table */}
            <div className="bg-[#0a0a0d] border border-border/40 rounded-2xl overflow-hidden">
              <table className="min-w-full divide-y divide-border/60">
                <thead className="bg-[#060608]">
                  <tr>
                    <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Display Name</th>
                    <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Model ID</th>
                    <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Provider</th>
                    <th className="px-6 py-3.5 text-right text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50 bg-[#0a0a0d]/20">
                  {models.map(m => (
                    <tr key={m.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-white">{m.display_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono text-emerald-400">{m.model_id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-muted-foreground uppercase font-semibold">{m.provider_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-xs">
                        <button
                          onClick={async () => {
                            if (!confirm("Are you sure?")) return;
                            await api.delete(`/admin/models/${m.id}`);
                            fetchDashboardData();
                          }}
                          className="px-2 py-1.5 bg-secondary hover:bg-red-500/20 hover:text-red-500 border border-border rounded-lg font-bold text-[10px] transition-all"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── TAB CONTENT: MCP TOOLS & SERVERS ───────────────────── */}
        {activeTab === "mcp" && (
          <div className="space-y-8 animate-in fade-in duration-200">
            {/* Add Server Panel */}
            <div className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Plus className="w-4 h-4 text-primary" /> Register New MCP Server
                </h3>
                <button
                  onClick={() => setShowAddMcp(!showAddMcp)}
                  className="px-3 py-1 bg-secondary hover:bg-secondary/75 text-white text-[10px] font-bold rounded-lg transition-all"
                >
                  {showAddMcp ? "Hide Registration Form" : "Open Registration Form"}
                </button>
              </div>

              {showAddMcp && (
                <div className="space-y-4 pt-2 border-t border-border/20">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Server Name</label>
                      <input
                        type="text"
                        placeholder="e.g. Brave Search"
                        value={newMcp.name}
                        onChange={e => setNewMcp(prev => ({ ...prev, name: e.target.value }))}
                        className="w-full bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Server Type</label>
                      <select
                        value={newMcp.server_type}
                        onChange={e => setNewMcp(prev => ({ ...prev, server_type: e.target.value }))}
                        className="w-full bg-[#08080a] border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                      >
                        <option value="sse">Remote SSE (HTTP Endpoint)</option>
                        <option value="command">Local Stdio (Subprocess / Command)</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Description</label>
                      <input
                        type="text"
                        placeholder="What tools does this server provide?"
                        value={newMcp.description}
                        onChange={e => setNewMcp(prev => ({ ...prev, description: e.target.value }))}
                        className="w-full bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                      />
                    </div>
                  </div>

                  {newMcp.server_type === "sse" ? (
                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">SSE Connection URL</label>
                      <input
                        type="text"
                        placeholder="https://search-mcp.company.com/sse"
                        value={newMcp.url}
                        onChange={e => setNewMcp(prev => ({ ...prev, url: e.target.value }))}
                        className="w-full bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                      />
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Stdio Command Line</label>
                      <input
                        type="text"
                        placeholder="npx -y @modelcontextprotocol/server-postgres --db-url ..."
                        value={newMcp.command}
                        onChange={e => setNewMcp(prev => ({ ...prev, command: e.target.value }))}
                        className="w-full bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                      />
                    </div>
                  )}

                  <div className="space-y-1">
                    <label className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">
                      Secure Configuration JSON / Authorization Headers (Optional)
                    </label>
                    <textarea
                      placeholder='{ "Authorization": "Bearer key_here", "DB_PASSWORD": "..." }'
                      value={newMcp.env_variables}
                      onChange={e => setNewMcp(prev => ({ ...prev, env_variables: e.target.value }))}
                      rows={3}
                      className="w-full bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-mono rounded-xl px-4 py-2.5 text-white outline-none resize-none"
                    />
                    <span className="text-[8px] text-muted-foreground/60 italic">Encrypted using AES-256-GCM before saving to database</span>
                  </div>

                  <button
                    onClick={handleAddMcpServer}
                    className="px-5 py-2.5 bg-primary hover:bg-primary/90 text-white text-xs font-bold rounded-xl select-none transition-all active:scale-[0.98]"
                  >
                    Register Server
                  </button>
                </div>
              )}
            </div>

            {/* List Registered Servers */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {mcpServers.map(s => {
                const tStatus = mcpTestStatus[s.id];
                const isEditing = editingMcpId === s.id;
                return (
                  <div key={s.id} className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl flex flex-col justify-between space-y-4">
                    {isEditing ? (
                      /* Editing View */
                      <div className="space-y-3">
                        <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-2">Edit MCP Server</h4>
                        
                        <div className="space-y-1">
                          <label className="text-[8px] font-bold text-muted-foreground uppercase">Server Name</label>
                          <input
                            type="text"
                            value={editingMcpData.name}
                            onChange={e => setEditingMcpData(prev => ({ ...prev, name: e.target.value }))}
                            className="w-full bg-secondary/20 border border-border/50 text-xs font-bold rounded-lg px-3 py-1.5 text-white outline-none"
                          />
                        </div>

                        <div className="space-y-1">
                          <label className="text-[8px] font-bold text-muted-foreground uppercase">Description</label>
                          <input
                            type="text"
                            value={editingMcpData.description}
                            onChange={e => setEditingMcpData(prev => ({ ...prev, description: e.target.value }))}
                            className="w-full bg-secondary/20 border border-border/50 text-xs font-bold rounded-lg px-3 py-1.5 text-white outline-none"
                          />
                        </div>

                        {s.server_type === "sse" ? (
                          <div className="space-y-1">
                            <label className="text-[8px] font-bold text-muted-foreground uppercase">SSE URL</label>
                            <input
                              type="text"
                              value={editingMcpData.url}
                              onChange={e => setEditingMcpData(prev => ({ ...prev, url: e.target.value }))}
                              className="w-full bg-secondary/20 border border-border/50 text-xs font-bold rounded-lg px-3 py-1.5 text-white outline-none"
                            />
                          </div>
                        ) : (
                          <div className="space-y-1">
                            <label className="text-[8px] font-bold text-muted-foreground uppercase">Command</label>
                            <input
                              type="text"
                              value={editingMcpData.command}
                              onChange={e => setEditingMcpData(prev => ({ ...prev, command: e.target.value }))}
                              className="w-full bg-secondary/20 border border-border/50 text-xs font-bold rounded-lg px-3 py-1.5 text-white outline-none"
                            />
                          </div>
                        )}

                        <div className="space-y-1">
                          <label className="text-[8px] font-bold text-muted-foreground uppercase">
                            Headers / Env JSON (optional)
                          </label>
                          <textarea
                            placeholder='{ "X-Goog-Api-Key": "..." }'
                            value={editingMcpData.env_variables}
                            onChange={e => setEditingMcpData(prev => ({ ...prev, env_variables: e.target.value }))}
                            rows={2}
                            className="w-full bg-secondary/20 border border-border/50 text-xs font-mono rounded-lg px-3 py-1.5 text-white outline-none resize-none"
                          />
                        </div>

                        <div className="flex gap-2 pt-2">
                          <button
                            onClick={() => handleSaveMcpEdit(s.id)}
                            className="flex-1 py-1.5 bg-primary hover:bg-primary/95 text-white text-[11px] font-bold rounded-lg transition-all active:scale-[0.97]"
                          >
                            Save Changes
                          </button>
                          <button
                            onClick={() => setEditingMcpId(null)}
                            className="px-3 py-1.5 bg-secondary hover:bg-secondary/75 text-white text-[11px] font-bold rounded-lg transition-all"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Display View */
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">🔌</span>
                            <div>
                              <h4 className="text-sm font-bold text-white uppercase tracking-wider">{s.name}</h4>
                              <span className="text-[8px] font-bold text-muted-foreground uppercase bg-secondary/30 border border-border/30 px-1.5 py-0.5 rounded-md">
                                {s.server_type}
                              </span>
                            </div>
                          </div>

                          <button
                            onClick={() => handleToggleMcpServer(s.id, s.is_enabled)}
                            className={`px-3 py-1.5 rounded-xl border text-[10px] font-bold uppercase transition-all ${
                              s.is_enabled
                                ? "bg-green-500/10 border-green-500/20 text-green-500 hover:bg-green-500/20"
                                : "bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20"
                            }`}
                          >
                            {s.is_enabled ? "Enabled" : "Disabled"}
                          </button>
                        </div>

                        {s.description && (
                          <p className="text-[11px] text-muted-foreground">{s.description}</p>
                        )}

                        <div className="p-2.5 rounded-xl bg-secondary/10 border border-border/30 space-y-1 font-mono text-[9px] text-gray-300">
                          <span className="text-muted-foreground uppercase font-bold tracking-wider block text-[8px] mb-1">Connection Details</span>
                          {s.server_type === "sse" ? (
                            <div className="truncate"><span className="text-primary font-bold">URL:</span> {s.url}</div>
                          ) : (
                            <div className="truncate"><span className="text-violet-400 font-bold">CMD:</span> {s.command}</div>
                          )}
                          {s.env_variables_encrypted && (
                            <div className="text-[8px] text-muted-foreground/60 italic">🔒 Encrypted parameters set</div>
                          )}
                        </div>

                        {/* Connection Test Output */}
                        {tStatus && (
                          <div className={`p-2.5 rounded-xl text-[10px] font-medium border ${
                            tStatus.status === "loading"
                              ? "bg-secondary/10 border-border animate-pulse text-muted-foreground"
                              : tStatus.status === "healthy"
                              ? "bg-green-500/5 border-green-500/15 text-emerald-400"
                              : "bg-red-500/5 border-red-500/15 text-red-400"
                          }`}>
                            {tStatus.status === "loading" && "⏳ Verifying connection..."}
                            {tStatus.status === "healthy" && `✅ Synced: ${tStatus.detail}`}
                            {tStatus.status === "error" && `❌ Connection failed: ${tStatus.detail}`}
                            {tStatus.status === "warning" && `⚠️ Warnings: ${tStatus.detail}`}
                          </div>
                        )}
                      </div>
                    )}

                    {!isEditing && (
                      <div className="flex gap-2 border-t border-border/20 pt-4">
                        <button
                          onClick={() => handleTestMcpServer(s.id)}
                          disabled={tStatus?.status === "loading"}
                          className="flex-1 py-2 bg-primary/10 hover:bg-primary/25 border border-primary/20 text-primary hover:text-white text-xs font-bold rounded-xl select-none transition-all active:scale-95 disabled:opacity-50"
                        >
                          {tStatus?.status === "loading" ? "Testing..." : "Test Connection"}
                        </button>
                        <button
                          onClick={() => {
                            setEditingMcpId(s.id);
                            setEditingMcpData({
                              name: s.name,
                              description: s.description || "",
                              server_type: s.server_type,
                              url: s.url || "",
                              command: s.command || "",
                              env_variables: "" // Keep blank so we don't overwrite with blank, only fill if they want to update it
                            });
                          }}
                          className="px-3.5 py-2 bg-secondary hover:bg-secondary/75 text-white text-xs font-bold rounded-xl select-none transition-all active:scale-95"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteMcpServer(s.id)}
                          className="px-3.5 py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 text-xs font-bold rounded-xl select-none transition-all active:scale-95"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}

              {mcpServers.length === 0 && (
                <div className="col-span-2 py-10 text-center bg-[#0a0a0d] border border-border/40 rounded-2xl flex flex-col items-center justify-center space-y-2 text-muted-foreground select-none">
                  <span className="text-3xl">🔌</span>
                  <p className="text-xs font-bold uppercase tracking-wider">No MCP Tools Registered</p>
                  <p className="text-[10px] font-semibold max-w-sm">Register SSE or Local commands to extend the AI Assistant's capabilities with real-time tools.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB CONTENT: BILLING & PLANS ──────────────────────── */}
        {activeTab === "billing" && (
          <div className="space-y-8 animate-in fade-in duration-200">
            {/* Create Plan Card */}
            <div className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl space-y-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Create Billing Plan</h3>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <input
                  type="text"
                  placeholder="Plan Name (e.g. Pro)"
                  value={newPlan.name}
                  onChange={e => setNewPlan(prev => ({ ...prev, name: e.target.value }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                />
                <input
                  type="number"
                  placeholder="Monthly Price ($)"
                  value={newPlan.price || ""}
                  onChange={e => setNewPlan(prev => ({ ...prev, price: parseFloat(e.target.value) || 0 }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                />
                <input
                  type="number"
                  placeholder="Monthly Token Quota"
                  value={newPlan.tokens || ""}
                  onChange={e => setNewPlan(prev => ({ ...prev, tokens: parseInt(e.target.value) || 0 }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                />
                <input
                  type="number"
                  placeholder="Monthly Messages Limit"
                  value={newPlan.msgs || ""}
                  onChange={e => setNewPlan(prev => ({ ...prev, msgs: parseInt(e.target.value) || 0 }))}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 text-white outline-none"
                />
                <button
                  onClick={handleAddPlan}
                  className="w-full py-2.5 bg-primary hover:bg-primary/95 text-white font-bold rounded-xl text-xs transition-all"
                >
                  Create Plan
                </button>
              </div>
            </div>

            {/* Plans List */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {plans.map(p => (
                <div key={p.id} className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl flex flex-col justify-between">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">{p.name} Plan</span>
                      <span className="text-xl font-extrabold text-primary">${p.monthly_price}/mo</span>
                    </div>

                    <div className="space-y-2 border-t border-border/25 pt-4">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">Token Limit:</span>
                        <span className="font-bold text-white">{p.monthly_token_limit.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">Message Limit:</span>
                        <span className="font-bold text-white">{p.monthly_message_limit} / mo</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground">File Upload Limit:</span>
                        <span className="font-bold text-white">{p.max_upload_size_mb} MB</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── TAB CONTENT: FILES REGISTRY ───────────────────────── */}
        {activeTab === "files" && (
          <div className="bg-[#0a0a0d] border border-border/40 rounded-2xl overflow-hidden animate-in fade-in duration-200">
            <table className="min-w-full divide-y divide-border/60">
              <thead className="bg-[#060608]">
                <tr>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Filename</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Uploader Email</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">File Size</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">MIME Type</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Uploaded At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50 bg-[#0a0a0d]/20">
                {files.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-xs text-muted-foreground">
                      No files uploaded to the platform registry
                    </td>
                  </tr>
                ) : (
                  files.map(f => (
                    <tr key={f.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-white max-w-xs truncate">{f.filename}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-muted-foreground">{f.user_email}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-white">{(f.file_size / 1024).toFixed(1)} KB</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono text-emerald-400">{f.mime_type}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-muted-foreground">{new Date(f.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ── TAB CONTENT: SUPPORT TICKETS ──────────────────────── */}
        {activeTab === "tickets" && (
          <div className="space-y-6 animate-in fade-in duration-200">
            {tickets.length === 0 ? (
              <div className="p-8 text-center bg-[#0a0a0d] border border-border/40 rounded-2xl text-xs text-muted-foreground">
                No active complaints or support tickets in queue
              </div>
            ) : (
              tickets.map(t => (
                <div key={t.id} className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-primary/10 border border-primary/20 text-[9px] font-bold text-primary uppercase tracking-wide">{t.category}</span>
                      <h3 className="text-sm font-bold text-white">{t.subject}</h3>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wide ${
                      t.status === "open" ? "bg-amber-500/10 border border-amber-500/20 text-amber-500" : "bg-green-500/10 border border-green-500/20 text-green-500"
                    }`}>{t.status}</span>
                  </div>

                  <p className="text-xs text-gray-400 font-medium leading-relaxed">{t.description}</p>

                  <div className="flex items-center justify-between border-t border-border/25 pt-4 mt-2">
                    <span className="text-[10px] text-muted-foreground">Uploader: <b className="text-white">{t.user_email}</b></span>
                    {t.status === "open" && (
                      <button
                        onClick={() => handleResolveTicket(t.id, "Resolved via admin console updates")}
                        className="px-3 py-1.5 bg-green-500/10 border border-green-500/20 hover:bg-green-500/20 text-green-500 rounded-lg text-[10px] font-bold uppercase transition-all"
                      >
                        Resolve Ticket
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── TAB CONTENT: SYSTEM CONFIG SETTINGS ───────────────── */}
        {activeTab === "settings" && (
          <div className="p-6 bg-[#0a0a0d] border border-border/40 rounded-2xl space-y-6 animate-in fade-in duration-200">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider border-b border-border/25 pb-3">Global Platform Configuration</h3>

            <div className="space-y-4 max-w-xl">
              {[
                { key: "platform_name", label: "Application Name", desc: "Change the UI banner name dynamically" },
                { key: "maintenance_mode", label: "Maintenance Mode", desc: "Toggle custom maintenance wall (true / false)" },
                { key: "signup_enabled", label: "Allow Signups", desc: "Toggle standard public user registrations (true / false)" }
              ].map(s => {
                const activeVal = settings.find(opt => opt.setting_key === s.key)?.setting_value || "";
                return (
                  <div key={s.key} className="space-y-1">
                    <label className="text-[11px] font-bold text-white uppercase tracking-wide block">{s.label}</label>
                    <input
                      type="text"
                      defaultValue={activeVal}
                      onBlur={e => handleUpdateSetting(s.key, e.target.value)}
                      placeholder="e.g. true or false"
                      className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-semibold rounded-xl px-4 py-2.5 w-full text-white outline-none"
                    />
                    <span className="text-[10px] text-muted-foreground/60 block">{s.desc}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── TAB CONTENT: AUDIT LOGS ────────────────────────────── */}
        {activeTab === "logs" && (
          <div className="bg-[#0a0a0d] border border-border/40 rounded-2xl overflow-hidden animate-in fade-in duration-200">
            <table className="min-w-full divide-y divide-border/60">
              <thead className="bg-[#060608]">
                <tr>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Timestamp</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Admin User</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Action Type</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Target</th>
                  <th className="px-6 py-3.5 text-left text-[10px] font-bold text-muted-foreground uppercase tracking-wider">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50 bg-[#0a0a0d]/20">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-xs text-muted-foreground">
                      No security audit events recorded yet
                    </td>
                  </tr>
                ) : (
                  auditLogs.map(log => (
                    <tr key={log.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString()}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-white">{log.admin_email}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-bold font-mono text-emerald-400">{log.action}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono text-muted-foreground max-w-xs truncate">{log.target_id || "N/A"}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono text-white">{log.ip_address}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ── MODAL: GRANT CREDITS ───────────────────────────────── */}
        {showCreditsModal && selectedUser && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200">
            <div className="bg-[#0c0c0e] border border-border/80 p-6 rounded-2xl w-96 space-y-4 max-w-md">
              <div className="flex items-center justify-between border-b border-border/30 pb-3">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Adjust Balance Credits</h3>
                <button onClick={() => setShowCreditsModal(false)} className="text-muted-foreground hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-muted-foreground block font-medium">Uploader Account</span>
                <span className="text-xs font-bold text-white">{selectedUser.email}</span>
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Credits Amount ($)</label>
                <input
                  type="number"
                  value={creditsToGrant}
                  onChange={e => setCreditsToGrant(parseFloat(e.target.value) || 0)}
                  className="bg-secondary/15 border border-border/60 focus:border-primary/50 text-xs font-bold rounded-xl px-4 py-2.5 w-full text-white outline-none"
                />
              </div>
              <button
                onClick={handleGrantCredits}
                className="w-full py-2.5 bg-primary hover:bg-primary/95 text-white font-bold rounded-xl text-xs transition-all"
              >
                Confirm Grant
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
