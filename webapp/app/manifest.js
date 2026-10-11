export default function manifest() {
  return { name: "AirGuard India", short_name: "AirGuard", description: "Current air-quality estimates and tomorrow's modelled forecast for India.", start_url: "/live", scope: "/", display: "standalone", background_color: "#f7f8f2", theme_color: "#17342b", icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }] };
}
