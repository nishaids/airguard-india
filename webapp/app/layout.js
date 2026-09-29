import { Outfit, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import NavBar from "./components/NavBar";

const display = Outfit({ subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-display", display: "swap" });
const body = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-body", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" });

export const metadata = {
  title: "AirGuard India",
  description:
    "A vulnerability-weighted Health Advisory Index and next-day air quality forecasting system for Indian cities.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <NavBar />
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
