"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/forecast", label: "Forecast" },
  { href: "/city-atlas", label: "City Risk Atlas" },
  { href: "/policy-simulator", label: "Policy Simulator" },
  { href: "/model-insights", label: "Model Insights" },
];

export default function NavBar() {
  const pathname = usePathname();
  return (
    <nav className="navbar">
      <span className="brand">🌬 AirGuard India</span>
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} className={pathname === link.href ? "active" : ""}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
