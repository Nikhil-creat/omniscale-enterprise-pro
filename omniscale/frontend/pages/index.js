// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useEffect, useState } from "react";
import { auth, billing, setToken, clearToken } from "../lib/api";

export default function Home() {
  const [user, setUser] = useState(null);
  const [usage, setUsage] = useState(null);
  const [sub, setSub] = useState(null);
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", fullName: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const me = await auth.me();
      setUser(me.data);
      const [usageRes, subRes] = await Promise.allSettled([billing.usage(), billing.subscription()]);
      if (usageRes.status === "fulfilled") setUsage(usageRes.value.data);
      if (subRes.status === "fulfilled") setSub(subRes.value.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      if (mode === "register") {
        await auth.register(form.email, form.password, form.fullName);
      }
      const res = await auth.login(form.email, form.password);
      setToken(res.data.access_token);
      await refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || "Something went wrong");
    }
  }

  function handleLogout() {
    clearToken();
    setUser(null);
    setUsage(null);
    setSub(null);
  }

  if (loading) return <div className="card">Loading…</div>;

  if (!user) {
    return (
      <div className="card" style={{ maxWidth: 420 }}>
        <h2>{mode === "login" ? "Sign in" : "Create your account"}</h2>
        {error && <div className="error-text">{error}</div>}
        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <input
              placeholder="Full name"
              value={form.fullName}
              onChange={(e) => setForm({ ...form, fullName: e.target.value })}
            />
          )}
          <input
            placeholder="Email"
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <input
            placeholder="Password"
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <button type="submit">{mode === "login" ? "Sign in" : "Register"}</button>
        </form>
        <p style={{ fontSize: 13, marginTop: 12 }}>
          {mode === "login" ? (
            <>No account? <a onClick={() => setMode("register")} style={{ cursor: "pointer" }}>Register</a></>
          ) : (
            <>Already have an account? <a onClick={() => setMode("login")} style={{ cursor: "pointer" }}>Sign in</a></>
          )}
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="card">
        <h2>Welcome, {user.full_name || user.email}</h2>
        <p style={{ color: "var(--muted)" }}>Multi-tenant AI SaaS control panel.</p>
        <button className="secondary" onClick={handleLogout}>Log out</button>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="metric-label">Subscription tier</div>
          <div className="metric">{sub ? sub.tier.toUpperCase() : "FREE"}</div>
          <span className={`badge ${sub?.status === "active" ? "success" : "muted"}`}>
            {sub?.status || "inactive"}
          </span>
        </div>
        <div className="card">
          <div className="metric-label">Requests this minute</div>
          <div className="metric">
            {usage ? `${usage.requests_this_minute} / ${usage.requests_limit_per_minute}` : "—"}
          </div>
        </div>
        <div className="card">
          <div className="metric-label">Documents indexed</div>
          <div className="metric">{usage ? usage.documents_indexed : "—"}</div>
        </div>
        <div className="card">
          <div className="metric-label">Jobs (24h)</div>
          <div className="metric">{usage ? usage.jobs_last_24h : "—"}</div>
        </div>
      </div>
    </div>
  );
}
