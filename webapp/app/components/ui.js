export function Metric({ label, value, delta, deltaGood, help }) {
  return (
    <div className="metric" title={help || ""}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {delta ? <div className={`delta ${deltaGood === true ? "good" : deltaGood === false ? "bad" : ""}`}>{delta}</div> : null}
    </div>
  );
}

export function Banner({ kind = "info", icon, children }) {
  return (
    <div className={`banner ${kind}`}>
      {icon ? `${icon} ` : ""}
      {children}
    </div>
  );
}

export function Table({ columns, rows }) {
  if (!rows || rows.length === 0) return <p className="caption">No data.</p>;
  const cols = columns || Object.keys(rows[0]);
  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{typeof row[c] === "number" ? formatNumber(row[c]) : String(row[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function formatNumber(value) {
  if (value === null || value === undefined) return "";
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function Figure({ src, caption }) {
  return (
    <figure style={{ margin: "10px 0" }}>
      <img className="figure" src={src} alt={caption || ""} />
      {caption ? <figcaption className="caption">{caption}</figcaption> : null}
    </figure>
  );
}
