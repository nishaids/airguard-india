"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { useOperational } from "./OperationalProvider";

const LINKS = [
  { href: "/live", label: "Live air quality" },
  { href: "/forecast", label: "Forecast & advisory" },
  { href: "/city-atlas", label: "Atlas" },
  { href: "/research", label: "Research" },
  { href: "/historical-replay", label: "Historical replay" },
  { href: "/policy-simulator", label: "Policy scenarios" },
  { href: "/model-insights", label: "Legacy models" },
  { href: "/methods", label: "Methods" },
  { href: "/status", label: "Status" },
];

export default function NavBar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { href } = useOperational();
  const operational = ["/live", "/forecast", "/city-atlas", "/policy-simulator", "/research"];
  return (
    <nav className="navbar" aria-label="Main navigation">
      <Link href={href("/live")} className="brand" style={{ color: "inherit" }}>
        <span className="brand-mark">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.1" strokeLinecap="round">
            <path d="M3 8h11a3 3 0 1 0-3-3" />
            <path d="M3 13h15a3 3 0 1 1-3 3" />
            <path d="M3 18h8" />
          </svg>
        </span>
        AirGuard India
      </Link>
      <button type="button" className="nav-toggle" aria-expanded={open} aria-controls="main-nav-links" onClick={() => setOpen(v => !v)}>{open ? "Close menu" : "Menu"}</button>
      <div id="main-nav-links" className={`nav-links${open ? " is-open" : ""}`} onKeyDown={event => { if (event.key === "Escape") setOpen(false); }}>
      {LINKS.map((link) => (
        <Link key={link.href} href={operational.includes(link.href) ? href(link.href) : link.href} onClick={() => setOpen(false)} aria-current={pathname === link.href ? "page" : undefined} className={pathname === link.href ? "active" : ""}>
          {link.label}
        </Link>
      ))}
      </div>
    </nav>
  );
}
