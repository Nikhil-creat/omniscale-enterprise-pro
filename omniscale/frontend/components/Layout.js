// OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
import Link from "next/link";
import { useRouter } from "next/router";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/agent", label: "Agent Console" },
  { href: "/documents", label: "RAG Documents" },
  { href: "/vision", label: "CNN Vision" },
  { href: "/billing", label: "Billing" },
];

export default function Layout({ children }) {
  const router = useRouter();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">OmniScale Enterprise Pro</div>
        <div className="brand-sub">Designed and Developed by NIKHIL CHARY SRIRAMOJU</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="nav-link"
              style={{
                background: router.pathname === item.href ? "rgba(99,102,241,0.18)" : "transparent",
              }}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">
        {children}
        <div className="footer">OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU</div>
      </main>
    </div>
  );
}
