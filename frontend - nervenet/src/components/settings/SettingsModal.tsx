import React, { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import api from "@/lib/api";
import { X, User, Key, CreditCard, Shield, Plus, Trash2 } from "lucide-react";

interface SettingsModalProps {
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ onClose }) => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"profile" | "keys" | "billing" | "sessions">("profile");

  // Profile Form States
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  // Custom API Keys States
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyValue, setNewKeyValue] = useState("");

  // Session States
  const [sessions, setSessions] = useState<any[]>([]);

  // Prepaid Wallet States
  const [balance, setBalance] = useState<number>(5.00);
  const [totalTokens, setTotalTokens] = useState<number>(0);
  const [topUpAmount, setTopUpAmount] = useState<number>(10);
  const [topUpLoading, setTopUpLoading] = useState(false);

  useEffect(() => {
    if (activeTab === "keys") {
      fetchApiKeys();
    } else if (activeTab === "sessions") {
      fetchSessions();
    } else if (activeTab === "billing") {
      fetchBalance();
    }
  }, [activeTab]);

  const fetchApiKeys = async () => {
    try {
      await api.get("/settings"); // Settings endpoints contain active configurations
      // Mock API Key responses from user keys database or render setting list
      setApiKeys([
        { id: "1", key_name: "My OpenAI Key", hashed_key: "sk-proj-••••••••" }
      ]);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchSessions = async () => {
    try {
      // In production, endpoints like /users/me/sessions fetch active listings
      setSessions([
        { id: "1", user_agent: "Chrome / macOS", ip_address: "127.0.0.1", created_at: new Date().toISOString() }
      ]);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchBalance = async () => {
    try {
      const res = await api.get("/payment/balance");
      setBalance(res.data.balance);
      setTotalTokens(res.data.total_tokens_used || 0);
    } catch (err) {
      console.error("Failed to load balance", err);
    }
  };

  const handleTopUp = async () => {
    setTopUpLoading(true);
    try {
      const res = await api.post("/payment/add-funds", { amount: topUpAmount });
      setBalance(res.data.balance);
      setTotalTokens(res.data.total_tokens_used || 0);
      alert(`Successfully added $${topUpAmount.toFixed(2)} to your wallet!`);
    } catch (err) {
      console.error("Top-up failed", err);
    } finally {
      setTopUpLoading(false);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccessMsg("");
    try {
      await api.put("/users/me", { full_name: fullName });
      setSuccessMsg("Profile updated successfully!");
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-3xl h-[32rem] dark:bg-[#0c0c0e] bg-card border border-border rounded-2xl flex overflow-hidden shadow-2xl relative animate-in zoom-in-95 duration-200">
        
        {/* Left Tabs Sidebar */}
        <div className="w-48 dark:bg-[#08080a] bg-muted/40 border-r border-border/40 p-4 space-y-1 select-none">
          <div className="text-[10px] font-bold text-muted-foreground/60 px-2.5 py-2 uppercase tracking-wider">
            User Settings
          </div>
          
          {[
            { id: "profile", label: "Profile", icon: User },
            { id: "keys", label: "Developer Keys", icon: Key },
            { id: "billing", label: "Billing & Plans", icon: CreditCard },
            { id: "sessions", label: "Security & Sessions", icon: Shield },
          ].map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as any)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  activeTab === t.id
                    ? "bg-primary text-white"
                    : "text-muted-foreground hover:bg-secondary/30 dark:hover:text-white hover:text-foreground"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Right Content Panel */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Modal Header */}
          <div className="h-14 border-b border-border/40 px-6 flex items-center justify-between select-none">
            <span className="text-sm font-bold dark:text-white text-gray-800 uppercase tracking-wider">{activeTab} settings</span>
            <button
              onClick={onClose}
              className="p-1 hover:bg-secondary rounded-lg text-muted-foreground hover:text-foreground transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Modal Tab Body */}
          <div className="flex-1 overflow-y-auto p-6">
            {successMsg && (
              <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-500 text-xs font-semibold">
                {successMsg}
              </div>
            )}

            {activeTab === "profile" && (
              <form onSubmit={handleUpdateProfile} className="space-y-4 max-w-md">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase">Email Address</label>
                  <input
                    type="email"
                    disabled
                    value={user?.email || ""}
                    className="w-full px-3.5 py-2.5 bg-secondary/20 border border-border/60 rounded-xl text-xs text-muted-foreground focus:outline-none"
                  />
                </div>
                
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase">Full Name</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Enter name"
                    className="w-full px-3.5 py-2.5 bg-secondary/40 border border-border rounded-xl text-xs dark:text-white text-gray-800 placeholder-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2.5 mt-2 bg-primary hover:bg-primary/95 text-white text-xs font-bold rounded-xl transition-all"
                >
                  {loading ? "Saving..." : "Save Changes"}
                </button>
              </form>
            )}

            {activeTab === "keys" && (
              <div className="space-y-6">
                <div className="space-y-3">
                  <h3 className="text-xs font-bold dark:text-white text-gray-800 uppercase tracking-wide">Add Custom API Key</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      type="text"
                      placeholder="Provider Name (e.g., openai)"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      className="px-3 py-2 bg-secondary/40 border border-border rounded-xl text-xs dark:text-white text-gray-800 focus:outline-none"
                    />
                    <input
                      type="password"
                      placeholder="API Key (sk-...)"
                      value={newKeyValue}
                      onChange={(e) => setNewKeyValue(e.target.value)}
                      className="px-3 py-2 bg-secondary/40 border border-border rounded-xl text-xs dark:text-white text-gray-800 focus:outline-none"
                    />
                  </div>
                  <button className="flex items-center gap-1.5 px-3 py-2 bg-primary text-white text-xs font-bold rounded-xl hover:bg-primary/90 transition-all">
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Key</span>
                  </button>
                </div>

                <div className="space-y-3">
                  <h3 className="text-xs font-bold dark:text-white text-gray-800 uppercase tracking-wide">Registered Developer Keys</h3>
                  <div className="space-y-2">
                    {apiKeys.map((key) => (
                      <div key={key.id} className="flex items-center justify-between p-3 bg-secondary/20 border border-border rounded-xl">
                        <div className="flex flex-col">
                          <span className="text-xs font-semibold dark:text-white text-gray-800">{key.key_name}</span>
                          <span className="text-[10px] font-mono text-muted-foreground">{key.hashed_key}</span>
                        </div>
                        <button className="p-1.5 text-muted-foreground hover:text-red-500 rounded-lg transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === "billing" && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Prepaid balance display card */}
                  <div className="p-5 rounded-2xl bg-secondary/20 border border-border/80 flex flex-col justify-between">
                    <div>
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Prepaid Wallet Balance</span>
                      <span className="text-2xl font-black text-emerald-400 mt-1 block">${balance.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-4">
                      <select
                        value={topUpAmount}
                        onChange={e => setTopUpAmount(parseInt(e.target.value) || 10)}
                        className="bg-secondary/40 border border-border/80 rounded-xl text-xs font-bold px-2 py-1.5 dark:text-white text-gray-800 outline-none"
                      >
                        <option value="10" className="dark:bg-stone-900 bg-white dark:text-white text-gray-800">$10 Credits</option>
                        <option value="25" className="dark:bg-stone-900 bg-white dark:text-white text-gray-800">$25 Credits</option>
                        <option value="50" className="dark:bg-stone-900 bg-white dark:text-white text-gray-800">$50 Credits</option>
                      </select>
                      <button
                        onClick={handleTopUp}
                        disabled={topUpLoading}
                        className="px-3 py-1.5 bg-primary hover:bg-primary/95 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-lg transition-all active:scale-[0.98]"
                      >
                        {topUpLoading ? "Adding..." : "Add"}
                      </button>
                    </div>
                  </div>

                  {/* Tokens consumed display card */}
                  <div className="p-5 rounded-2xl bg-secondary/20 border border-border/80 flex flex-col justify-between">
                    <div>
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Total LLM Tokens Used</span>
                      <span className="text-2xl font-black text-violet-400/90 mt-1 block">
                        {totalTokens.toLocaleString()}
                      </span>
                    </div>
                    <span className="text-[9px] text-muted-foreground/60 italic mt-4">Aggregated from query history logs</span>
                  </div>
                </div>

                {/* Token Pricing reference */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold dark:text-white text-gray-800 uppercase tracking-wide">Prepaid Token Pricing</h3>
                  <div className="p-4 rounded-2xl border border-border/60 space-y-3.5 dark:bg-[#09090c] bg-secondary/15">
                    <div className="flex justify-between items-center text-xs">
                      <div className="flex flex-col">
                        <span className="font-bold dark:text-white text-gray-800">Claude 3.5 Sonnet</span>
                        <span className="text-[10px] text-muted-foreground">General-purpose visual & code intelligence</span>
                      </div>
                      <span className="font-mono text-emerald-400 font-bold">$0.003 / 1k In | $0.015 / 1k Out</span>
                    </div>
                    <div className="h-px bg-border/25" />
                    <div className="flex justify-between items-center text-xs">
                      <div className="flex flex-col">
                        <span className="font-bold dark:text-white text-gray-800">GPT-4o Mini</span>
                        <span className="text-[10px] text-muted-foreground">High-speed reasoning model</span>
                      </div>
                      <span className="font-mono text-emerald-400 font-bold">$0.00015 / 1k In | $0.0006 / 1k Out</span>
                    </div>
                    <div className="h-px bg-border/25" />
                    <div className="flex justify-between items-center text-xs">
                      <div className="flex flex-col">
                        <span className="font-bold dark:text-white text-gray-800">Google Gemini Pro</span>
                        <span className="text-[10px] text-muted-foreground">Multimodal query handling</span>
                      </div>
                      <span className="font-mono text-emerald-400 font-bold">$0.00125 / 1k In | $0.005 / 1k Out</span>
                    </div>
                  </div>
                  <p className="text-[9.5px] text-muted-foreground/60 italic leading-normal text-center">
                    Charges are computed per query based on exact API token consumption. There are no monthly fees.
                  </p>
                </div>
              </div>
            )}

            {activeTab === "sessions" && (
              <div className="space-y-4">
                <h3 className="text-xs font-bold dark:text-white text-gray-800 uppercase tracking-wide mb-3">Logged Sessions</h3>
                <div className="space-y-2">
                  {sessions.map((sess) => (
                    <div key={sess.id} className="flex items-center justify-between p-3 bg-secondary/20 border border-border rounded-xl">
                      <div className="flex flex-col">
                        <span className="text-xs font-semibold dark:text-white text-gray-800">{sess.user_agent}</span>
                        <span className="text-[10px] text-muted-foreground mt-0.5">IP: {sess.ip_address} | Logged: {new Date(sess.created_at).toLocaleDateString()}</span>
                      </div>
                      <button className="text-[10px] font-bold text-red-500 hover:underline">
                        Revoke
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
