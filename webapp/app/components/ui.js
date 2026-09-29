export function Metric({ label, value, delta, deltaGood, help, hero }) {
  return (
    <div className={`metric${hero ? " metric-hero" : ""}`} title={help || ""}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {delta ? (
        <div className={`delta ${deltaGood === true ? "good" : deltaGood === false ? "bad" : ""}`}>{delta}</div>
      ) : null}
    </div>
  );
}

export function Banner({ kind = "info", icon, children }) {
  const fallback = { info: "ℹ", warn: "⚠", error: "⛔", success: "✓" }[kind];
  return (
    <div className={`banner ${kind}`}>
      <span className="banner-icon">{icon || fallback}</span>
      <div>{children}</div>
    </div>
  );
}

export function formatNumber(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

export function Table({ columns, rows, heat }) {
  if (!rows || rows.length === 0) return <p className="caption">No data.</p>;
  const cols = columns || Object.keys(rows[0]);

  const ranges = {};
  (heat || []).forEach((col) => {
    const values = rows.map((r) => r[col]).filter((v) => typeof v === "number");
    if (values.length) ranges[col] = [Math.min(...values), Math.max(...values)];
  });

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map((c) => {
                let style;
                if (ranges[c] && typeof row[c] === "number") {
                  const [lo, hi] = ranges[c];
                  const t = hi === lo ? 0 : (row[c] - lo) / (hi - lo);
                  style = { background: `rgba(213, 94, 0, ${0.05 + 0.32 * t})` };
                }
                return (
                  <td key={c} style={style}>
                    {typeof row[c] === "number" || typeof row[c] === "boolean"
                      ? formatNumber(row[c])
                      : String(row[c] ?? "")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Figure({ src, caption }) {
  return (
    <figure>
      <img className="figure" src={src} alt={caption || ""} loading="lazy" />
      {caption ? <figcaption className="caption">{caption}</figcaption> : null}
    </figure>
  );
}

export function Badge({ children, colour }) {
  return (
    <span className="badge" style={colour ? { borderColor: colour, color: colour } : undefined}>
      {colour ? <span style={{ width: 7, height: 7, borderRadius: 99, background: colour }} /> : null}
      {children}
    </span>
  );
}

export function Loading({ rows = 3 }) {
  return (
    <div className="loading-wrap" aria-busy="true" aria-label="Loading">
      <div className="skeleton" style={{ height: 34, width: "38%" }} />
      <div className="grid grid-4">
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton" style={{ height: 92 }} />)}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 150 }} />
      ))}
    </div>
  );
}

export function SectionTitle({ eyebrow, children, caption }) {
  return (
    <div style={{ marginTop: 34 }}>
      {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
      <h2 style={{ marginTop: 0 }}>{children}</h2>
      {caption ? <p className="caption" style={{ maxWidth: "80ch" }}>{caption}</p> : null}
    </div>
  );
}

/** Minimal Markdown renderer for the data and model cards. */
export function Markdown({ text }) {
  if (!text) return null;
  const blocks = [];
  const lines = text.split("\n");
  let i = 0;
  let key = 0;

  const inline = (s) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');

  while (i < lines.length) {
    const line = lines[i];

    if (/^\s*$/.test(line)) { i++; continue; }

    if (line.trimStart().startsWith("```")) {
      i++;
      const code = [];
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) { code.push(lines[i]); i++; }
      i++; // closing fence
      blocks.push(<pre key={key++}>{code.join("\n")}</pre>);
      continue;
    }

    if (/^\s*(---|===|\*\*\*)\s*$/.test(line)) {
      blocks.push(<hr key={key++} style={{ border: 0, borderTop: "1px solid var(--border)", margin: "22px 0" }} />);
      i++;
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      const Tag = `h${Math.min(heading[1].length + 1, 4)}`;
      blocks.push(<Tag key={key++} dangerouslySetInnerHTML={{ __html: inline(heading[2]) }} />);
      i++;
      continue;
    }

    if (line.startsWith("|")) {
      const table = [];
      while (i < lines.length && lines[i].startsWith("|")) { table.push(lines[i]); i++; }
      const parse = (r) => r.split("|").slice(1, -1).map((c) => c.trim());
      const header = parse(table[0]);
      const bodyRows = table.slice(2).map(parse);
      blocks.push(
        <div className="table-wrap" key={key++}>
          <table>
            <thead><tr>{header.map((h, n) => <th key={n} dangerouslySetInnerHTML={{ __html: inline(h) }} />)}</tr></thead>
            <tbody>
              {bodyRows.map((r, n) => (
                <tr key={n}>{r.map((c, m) => <td key={m} dangerouslySetInnerHTML={{ __html: inline(c) }} />)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (/^\s*>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) { quote.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
      blocks.push(<blockquote key={key++} dangerouslySetInnerHTML={{ __html: inline(quote.join(" ")) }} />);
      continue;
    }

    if (/^\s*(\d+\.|[-*])\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && /^\s*(\d+\.|[-*])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*(\d+\.|[-*])\s+/, ""));
        i++;
      }
      const Tag = ordered ? "ol" : "ul";
      blocks.push(
        <Tag key={key++}>
          {items.map((it, n) => <li key={n} dangerouslySetInnerHTML={{ __html: inline(it) }} />)}
        </Tag>
      );
      continue;
    }

    const stops = (s) =>
      /^\s*$/.test(s) ||
      s.startsWith("|") ||
      /^#{1,4}\s/.test(s) ||
      /^\s*>/.test(s) ||
      /^\s*(\d+\.|[-*])\s+/.test(s) ||
      s.trimStart().startsWith("```");

    const para = [];
    while (i < lines.length && !stops(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(<p key={key++} dangerouslySetInnerHTML={{ __html: inline(para.join(" ")) }} />);
  }

  return <div className="md">{blocks}</div>;
}
