// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useEffect, useState } from "react";
import { rag } from "../lib/api";

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState("");
  const [namespace, setNamespace] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");

  async function loadDocs() {
    try {
      const res = await rag.list();
      setDocs(res.data);
      if (res.data.length && !namespace) setNamespace(res.data[0].vector_namespace);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not load documents.");
    }
  }

  useEffect(() => {
    loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await rag.upload(file);
      await loadDocs();
    } catch (err) {
      setError(err?.response?.data?.detail || "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleQuery(e) {
    e.preventDefault();
    if (!query.trim() || !namespace) return;
    try {
      const res = await rag.query(query, namespace);
      setResults(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Query failed.");
    }
  }

  return (
    <div>
      <div className="card">
        <h2>RAG Documents</h2>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          Upload text documents to index them into your private vector namespace. Ingestion runs
          asynchronously via Celery — refresh to see updated chunk counts.
        </p>
        {error && <div className="error-text">{error}</div>}
        <input type="file" accept=".txt,.md" onChange={handleUpload} disabled={uploading} />
        {uploading && <span>Uploading…</span>}

        <table style={{ width: "100%", marginTop: 16, fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--muted)" }}>
              <th>Filename</th>
              <th>Chunks</th>
              <th>Namespace</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.filename}</td>
                <td>{d.chunk_count}</td>
                <td>{d.vector_namespace}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Query documents</h3>
        <form onSubmit={handleQuery} style={{ display: "flex", gap: 8 }}>
          <input
            placeholder="Ask a question about your documents…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ marginBottom: 0 }}
          />
          <button type="submit">Search</button>
        </form>
        {results.map((r, i) => (
          <div key={i} className="chat-bubble">
            <div style={{ fontSize: 12, color: "var(--muted)" }}>
              {r.source_document} · score {r.score.toFixed(3)}
            </div>
            {r.chunk_text}
          </div>
        ))}
      </div>
    </div>
  );
}
