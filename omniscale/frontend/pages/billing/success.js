// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { billing } from "../../lib/api";

export default function BillingSuccess() {
  const router = useRouter();
  const [sub, setSub] = useState(null);

  useEffect(() => {
    if (!router.isReady) return;
    // Give the Stripe webhook a moment to land before polling subscription state.
    const t = setTimeout(() => {
      billing.subscription().then((res) => setSub(res.data)).catch(() => {});
    }, 2000);
    return () => clearTimeout(t);
  }, [router.isReady]);

  return (
    <div className="card" style={{ maxWidth: 480 }}>
      <h2>Payment successful 🎉</h2>
      <p style={{ color: "var(--muted)" }}>
        Your subscription is being activated. This updates automatically once Stripe's webhook is
        processed — usually within a few seconds.
      </p>
      {sub && (
        <p>
          Current plan: <span className="badge success">{sub.tier.toUpperCase()}</span>
        </p>
      )}
      <button onClick={() => router.push("/")}>Back to dashboard</button>
    </div>
  );
}
