import "./globals.css";
import NavBar from "./components/NavBar";

export const metadata = {
  title: "AirGuard India",
  description:
    "A vulnerability-weighted Health Advisory Index and next-day air quality forecasting system for Indian cities.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        <div className="page">{children}</div>
      </body>
    </html>
  );
}
