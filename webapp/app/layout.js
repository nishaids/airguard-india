import { Outfit, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import NavBar from "./components/NavBar";
import OperationalProvider from "./components/OperationalProvider";

const display = Outfit({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display", display: "swap" });
const body = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-body", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" });

export const metadata = {
  metadataBase: new URL("https://webapp-phi-taupe.vercel.app"),
  title: "AirGuard India",
  description:
    "Nationwide Indian air-quality estimates and tomorrow's modelled forecast, with CPCB-style calculations, station context and traceable sources.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
  openGraph: { title: "AirGuard India", description: "Today's air and tomorrow's modelled forecast, with traceable sources and honest uncertainty.", url: "/live", type: "website", locale: "en_IN" },
  twitter: { card: "summary", title: "AirGuard India", description: "Current air-quality estimates and tomorrow's modelled forecast for India." },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <a href="#main-content" className="skip-link">Skip to air quality</a>
        <OperationalProvider><NavBar />
        <main id="main-content" className="page">{children}</main></OperationalProvider>
      </body>
    </html>
  );
}
