// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useEffect, useState } from "react";
import { billing } from "../lib/api";

const PLANS = [
  { id: "free", name: "Free", price: "$0", blurb: "20 req/min, community support" },
  { id: "pro", name: "Pro", price: "$29/mo", blurb: "120 req/min, priority queue" },
  { id: "enterprise", name: "Enterprise", price: "Custom", blurb: "600 req/min, dedicated support" },
];

export default function Billing() {
  const [sub, setSub] = useState(null);
  const [error, setError] = useState("");
  const [loadingTier, setLoadingTier] = useState(null);

  useEffect(() => {
    billing.subscription().then((res) => setSub(res.data)).catch(() => {});
  }, []);

  async function handleUpgrade(tier) {
    if (tier === "free") return;
    setError("");
    setLoadingTier(tier);
    try {
      const res = await billing.checkout(tier);
      window.location.href = res.data.checkout_url;
    } catch (err) {
      setError(err?.response?.data?.detail || "Checkout could not be started.");
    } finally {
      setLoadingTier(null);
    }
  }

  return (
    <div>
      <div className="card">
        <h2>Billing</h2>
        {error && <div className="error-text">{error}</div>}
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          Current plan:{" "}
          <span className="badge success">{sub ? sub.tier.toUpperCase() : "FREE"}</span>
        </p>
      </div>

      <div className="grid-2">
        {PLANS.map((plan) => (
          <div key={plan.id} className="card">
            <h3>{plan.name}</h3>
            <div className="metric">{plan.price}</div>
            <p style={{ color: "var(--muted)", fontSize: 13 }}>{plan.blurb}</p>
            <button
              disabled={plan.id === "free" || loadingTier === plan.id}
              onClick={() => handleUpgrade(plan.id)}
            >
              {plan.id === "free" ? "Current default" : loadingTier === plan.id ? "Redirecting…" : `Upgrade to ${plan.name}`}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
