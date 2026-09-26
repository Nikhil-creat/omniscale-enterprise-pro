// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import { useRouter } from "next/router";

export default function BillingCancel() {
  const router = useRouter();
  return (
    <div className="card" style={{ maxWidth: 480 }}>
      <h2>Checkout canceled</h2>
      <p style={{ color: "var(--muted)" }}>No charge was made. You can try again anytime.</p>
      <button onClick={() => router.push("/billing")}>Back to plans</button>
    </div>
  );
}
