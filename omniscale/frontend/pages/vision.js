// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useEffect, useRef, useState } from "react";
import { cnn } from "../lib/api";

export default function Vision() {
  const [job, setJob] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const pollRef = useRef(null);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setError("");
    setPreview(URL.createObjectURL(file));
    try {
      const res = await cnn.analyze(file);
      setJob(res.data);
      pollRef.current = setInterval(async () => {
        const poll = await cnn.getJob(res.data.id);
        setJob(poll.data);
        if (["succeeded", "failed"].includes(poll.data.status)) {
          clearInterval(pollRef.current);
        }
      }, 1500);
    } catch (err) {
      setError(err?.response?.data?.detail || "Analysis request failed.");
    }
  }

  const result = job?.result_json ? JSON.parse(job.result_json) : null;

  return (
    <div className="card">
      <h2>CNN Vision Pipeline</h2>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        Images are processed by a PyTorch CNN backbone in a background worker — this page polls
        the job until it completes.
      </p>
      {error && <div className="error-text">{error}</div>}
      <input type="file" accept="image/*" onChange={handleUpload} />

      {preview && (
        <img src={preview} alt="preview" style={{ maxWidth: 260, borderRadius: 8, marginTop: 16 }} />
      )}

      {job && (
        <div style={{ marginTop: 16 }}>
          <span
            className={`badge ${
              job.status === "succeeded" ? "success" : job.status === "failed" ? "danger" : "muted"
            }`}
          >
            {job.status}
          </span>
          {result?.predictions && (
            <table style={{ width: "100%", marginTop: 12, fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th>Label</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {result.predictions.map((p, i) => (
                  <tr key={i}>
                    <td>{p.label}</td>
                    <td>{(p.confidence * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {job.error_message && <div className="error-text">{job.error_message}</div>}
        </div>
      )}
    </div>
  );
}
