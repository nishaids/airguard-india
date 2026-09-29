// Okabe-Ito palette: colour-blind safe, used for every data encoding in the
// project so the web application, the figures and the reports agree.
export const DATA = {
  blue: "#0072B2",
  vermillion: "#D55E00",
  green: "#009E73",
  purple: "#CC79A7",
  orange: "#E69F00",
  sky: "#56B4E9",
  yellow: "#F0E442",
};

export const PALETTE = [DATA.blue, DATA.vermillion, DATA.green, DATA.purple, DATA.orange, DATA.sky, DATA.yellow];

export const BAND_COLOUR = {
  Low: "#009E73",
  Moderate: "#F0E442",
  High: "#E69F00",
  "Very High": "#D55E00",
  Extreme: "#CC79A7",
};

export const BUCKET_COLOUR = {
  Good: "#009E73",
  Satisfactory: "#5FCFA8",
  Moderate: "#F0E442",
  Poor: "#E69F00",
  "Very Poor": "#D55E00",
  Severe: "#A11B3B",
};

export const axisTick = { fill: "#7e8899", fontSize: 11 };

export const tooltipStyle = {
  background: "rgba(11,14,21,0.96)",
  border: "1px solid rgba(255,255,255,0.14)",
  borderRadius: 12,
  fontSize: 12.5,
  boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
  color: "#eef1f6",
};

export const tooltipProps = {
  contentStyle: tooltipStyle,
  itemStyle: { color: "#eef1f6" },
  labelStyle: { color: "#b6bfcd", fontWeight: 600, marginBottom: 4 },
  cursor: { fill: "rgba(255,255,255,0.04)" },
};
