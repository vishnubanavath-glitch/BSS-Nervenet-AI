import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { UserPlus, Mail, Lock, User } from "lucide-react";
import logo from "@/assets/logo.png";
import logoLight from "@/assets/logo_light.png";
import { useEffect } from "react";

export const Register: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const { register, error, loading } = useAuth();
  const navigate = useNavigate();

  const [activeTheme, setActiveTheme] = useState<"light" | "dark">(
    document.documentElement.classList.contains("dark") ? "dark" : "light"
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setActiveTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !fullName) return;
    const success = await register(email, password, fullName);
    if (success) {
      navigate("/");
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center bg-background px-4 overflow-hidden">
      {/* Background neon glows */}
      <div className="absolute top-[-20%] left-[-20%] w-[60%] h-[60%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-20%] w-[60%] h-[60%] rounded-full bg-indigo-500/10 blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md p-8 rounded-2xl glass relative z-10 shadow-2xl transition-all duration-300">
        <div className="text-center mb-8 flex flex-col items-center">
          <img src={activeTheme === "dark" ? logo : logoLight} alt="Bharat Smart Services Logo" className="h-10 w-auto object-contain mb-4 select-none" />
          <h2 className="text-3xl font-extrabold dark:text-white text-gray-800 tracking-tight">Nervenet AI</h2>
          <p className="text-muted-foreground text-sm mt-2">Sign up to begin chatting with cloud LLMs</p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-destructive/15 border border-destructive/20 text-destructive text-sm font-medium animate-shake">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-muted-foreground">Full Name</label>
            <div className="relative">
              <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="John Doe"
                className="w-full pl-11 pr-4 py-3 bg-secondary/40 border border-border rounded-xl text-white placeholder-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all duration-200"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-muted-foreground">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@domain.com"
                className="w-full pl-11 pr-4 py-3 bg-secondary/40 border border-border rounded-xl text-white placeholder-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all duration-200"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-muted-foreground">Password</label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 6 characters"
                className="w-full pl-11 pr-4 py-3 bg-secondary/40 border border-border rounded-xl text-white placeholder-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all duration-200"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 mt-2 bg-primary hover:bg-primary/95 text-white font-bold rounded-xl transition-all duration-200 disabled:opacity-50 shadow-[0_4px_20px_rgba(139,92,246,0.3)] active:scale-[0.98]"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                <UserPlus className="w-5 h-5" />
                <span>Sign Up</span>
              </>
            )}
          </button>
        </form>

        <div className="text-center mt-8 text-sm text-muted-foreground font-medium">
          Already have an account?{" "}
          <Link to="/login" className="text-primary hover:underline font-bold">
            Log In
          </Link>
        </div>
      </div>
    </div>
  );
};
