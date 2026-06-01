import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { api, currentMonth, formatMoney } from "../api.js";

// Wood-tone palette to match the rest of the UI.
const COLORS = ["#8b5a2b", "#c19a6b", "#a4774f", "#6b3410", "#d4a373", "#5d3a1a", "#b8860b"];

// Monthly analysis: headline total, vs-last-month, category breakdown, per-day trend,
// and top merchants.
export default function Analysis() {
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState(null);

  useEffect(() => {
    api.getAnalysis(month).then(setData).catch(() => {});
  }, [month]);

  if (!data) return <p className="muted">Loading…</p>;

  const delta = Number(data.delta_vs_previous);
  const byDay = data.by_day.map((d) => ({ day: d.day, total: Number(d.total) }));
  const byCategory = data.by_category.map((c) => ({
    name: c.category,
    value: Number(c.total),
  }));

  return (
    <div>
      <h1>Analysis</h1>
      <input
        type="month"
        value={month}
        onChange={(e) => setMonth(e.target.value)}
        style={{ marginBottom: 12 }}
      />

      <div className="card">
        <div className="muted">Total spent</div>
        <div className="stat">{formatMoney(data.total)}</div>
        <div className={`delta ${delta > 0 ? "up" : "down"}`}>
          {delta > 0 ? "⬆" : "⬇"} {formatMoney(Math.abs(delta))} vs last month
        </div>
        <div className="muted" style={{ marginTop: 4 }}>
          {data.transaction_count} transactions
        </div>
      </div>

      {byCategory.length > 0 && (
        <div className="card">
          <div className="muted">By category</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={byCategory} dataKey="value" nameKey="name" outerRadius={80} label>
                {byCategory.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => formatMoney(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {byDay.length > 0 && (
        <div className="card">
          <div className="muted">Spend by day</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={byDay}>
              <XAxis dataKey="day" stroke="#5d3a1a" fontSize={10} />
              <Tooltip formatter={(v) => formatMoney(v)} />
              <Bar dataKey="total" fill="#6b3410" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.top_merchants.length > 0 && (
        <div className="card">
          <div className="muted" style={{ marginBottom: 8 }}>Top merchants</div>
          {data.top_merchants.map((m) => (
            <div className="row" key={m.merchant} style={{ padding: "4px 0" }}>
              <span>{m.merchant}</span>
              <span className="amount">{formatMoney(m.total)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
