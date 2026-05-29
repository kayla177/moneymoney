import { useEffect, useMemo, useState } from "react";
import { api, currentMonth, formatMoney } from "../api.js";

// Searchable, month-scoped list of all transactions.
export default function Transactions({ categories }) {
  const [month, setMonth] = useState(currentMonth());
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.getTransactions({ month }).then(setItems).catch(() => {});
  }, [month]);

  const catName = useMemo(() => {
    const map = {};
    categories.forEach((c) => (map[c.id] = c.name));
    return map;
  }, [categories]);

  const filtered = items.filter((t) =>
    t.raw_merchant.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div>
      <h1>Transactions</h1>
      <div className="row" style={{ marginBottom: 12 }}>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
        <input
          placeholder="Search merchant…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {filtered.length === 0 && <div className="empty">No transactions.</div>}
      {filtered.map((t) => (
        <div className="card" key={t.id}>
          <div className="row">
            <span className="merchant">{t.raw_merchant || "(no merchant)"}</span>
            <span className="amount">{formatMoney(t.amount, t.currency)}</span>
          </div>
          <div className="row">
            <span className="muted">{new Date(t.date).toLocaleDateString()}</span>
            <span className={`tag ${t.status === "needs_review" ? "review" : ""}`}>
              {catName[t.category_id] || "Uncategorized"}
            </span>
          </div>
          {t.note && <p className="muted" style={{ margin: "8px 0 0" }}>{t.note}</p>}
        </div>
      ))}
    </div>
  );
}
