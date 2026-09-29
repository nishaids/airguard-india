"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/forecast", label: "Forecast" },
  { href: "/city-atlas", label: "City Risk Atlas" },
  { href: "/policy-simulator", label: "Policy Simulator" },
  { href: "/model-insights", label: "Model Insights" },
];

export default function NavBar() {
  const pathname = usePathname();
  return (
    <nav className="navbar">
      <Link href="/" className="brand" style={{ color: "inherit" }}>
        <span className="brand-mark">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.1" strokeLinecap="round">
            <path d="M3 8h11a3 3 0 1 0-3-3" />
            <path d="M3 13h15a3 3 0 1 1-3 3" />
            <path d="M3 18h8" />
          </svg>
        </span>
        AirGuard India
      </Link>
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className={pathname === link.href ? "active" : ""}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
