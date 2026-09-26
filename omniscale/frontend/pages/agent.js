// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useState } from "react";
import { agent } from "../lib/api";

export default function AgentConsole() {
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSend(e) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setError("");
    const userMsg = { role: "user", content: prompt };
    setMessages((prev) => [...prev, userMsg]);
    setPrompt("");
    setLoading(true);
    try {
      const res = await agent.invoke(userMsg.content);
      const { route_taken, answer, provider, sources, latency_ms } = res.data;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: answer, route: route_taken, provider, sources, latency: latency_ms },
      ]);
    } catch (err) {
      setError(err?.response?.data?.detail || "The agent request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h2>Autonomous Agent Console</h2>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        Requests are automatically routed to RAG retrieval, CNN vision, or direct chat.
      </p>
      {error && <div className="error-text">{error}</div>}

      <div style={{ marginBottom: 16 }}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            <strong>{m.role === "user" ? "You" : "OmniScale Agent"}</strong>
            {m.route && (
              <span className="badge muted" style={{ marginLeft: 8 }}>
                {m.route} · {m.provider} · {m.latency}ms
              </span>
            )}
            <div>{m.content}</div>
            {m.sources?.length > 0 && (
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
                Sources: {m.sources.join(", ")}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="chat-bubble">Thinking…</div>}
      </div>

      <form onSubmit={handleSend} style={{ display: "flex", gap: 8 }}>
        <input
          placeholder="Ask anything — reference your documents or just chat…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ marginBottom: 0 }}
        />
        <button type="submit" disabled={loading}>Send</button>
      </form>
    </div>
  );
}
