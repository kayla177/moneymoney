import { useEffect, useMemo, useState } from "react";
import { api, currentMonth, formatMoney } from "../api.js";
import { iconFor } from "../categoryIcons.js";
import CategoryPicker from "./CategoryPicker.jsx";

// Searchable, month-scoped list of all transactions. Tap one to recategorize or edit it.
export default function Transactions({ categories, onCreateCategory }) {
  const [month, setMonth] = useState(currentMonth());
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState(null);

  const load = () => {
    api.getTransactions({ month }).then(setItems).catch(() => {});
  };
  useEffect(load, [month]);

  const catName = useMemo(() => {
    const map = {};
    categories.forEach((c) => (map[c.id] = c.name));
    return map;
  }, [categories]);

  const filtered = items.filter((t) =>
    t.raw_merchant.toLowerCase().includes(query.toLowerCase())
  );

  const saveEdit = async (id, body) => {
    await api.updateTransaction(id, body);
    setEditingId(null);
    load();
  };

  return (
    <div>
      <h1>Transactions</h1>
      <div className="row" style={{ marginBottom: 12 }}>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        <input
          placeholder="Search merchant…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {filtered.length === 0 && <div className="empty">No transactions.</div>}
      {filtered.map((t) => (
        <div className="card" key={t.id}>
          <div
            className="row"
            onClick={() => setEditingId(editingId === t.id ? null : t.id)}
            style={{ cursor: "pointer" }}
          >
            <span className="merchant">{t.raw_merchant || "(no merchant)"}</span>
            <span className="amount">{formatMoney(t.amount, t.currency)}</span>
          </div>
          <div
            className="row"
            onClick={() => setEditingId(editingId === t.id ? null : t.id)}
            style={{ cursor: "pointer" }}
          >
            <span className="muted">{new Date(t.date).toLocaleDateString()}</span>
            <span className={`tag ${t.status === "needs_review" ? "review" : ""}`}>
              {t.category_id
                ? `${iconFor(catName[t.category_id])} ${catName[t.category_id]}`
                : "Uncategorized"}
            </span>
          </div>
          {t.note && editingId !== t.id && (
            <p className="muted" style={{ margin: "8px 0 0" }}>{t.note}</p>
          )}

          {editingId === t.id && (
            <EditRow
              txn={t}
              categories={categories}
              onSave={saveEdit}
              onCreateCategory={onCreateCategory}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function EditRow({ txn, categories, onSave, onCreateCategory }) {
  const [name, setName] = useState(txn.raw_merchant || "");
  const [cat, setCat] = useState(txn.category_id);
  const [sub, setSub] = useState(txn.subcategory_id);
  const [note, setNote] = useState(txn.note || "");
  const [learn, setLearn] = useState(false);

  return (
    <div style={{ marginTop: 12 }}>
      <label className="muted">Name</label>
      <input
        placeholder="Transaction name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ width: "100%", margin: "4px 0 12px" }}
      />
      <CategoryPicker
        categories={categories}
        selectedCategory={cat}
        selectedSub={sub}
        onCreateCategory={onCreateCategory}
        onPick={(c, s) => {
          setCat(c);
          setSub(s);
        }}
      />
      <input
        placeholder="Note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        style={{ width: "100%", margin: "12px 0" }}
      />
      <div className="row">
        {/* "Remember" learns a merchant -> category mapping, so it needs both a
            name to match on and a category to apply. */}
        {name.trim() && cat ? (
          <label className="muted">
            <input
              type="checkbox"
              checked={learn}
              onChange={(e) => setLearn(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            Remember
          </label>
        ) : (
          <span />
        )}
        <button
          className="primary"
          disabled={!name.trim() && !cat}
          onClick={() =>
            onSave(txn.id, {
              raw_merchant: name,
              category_id: cat,
              subcategory_id: sub,
              note: note || null,
              learn: name.trim() && cat ? learn : false,
            })
          }
        >
          SAVE
        </button>
      </div>
    </div>
  );
}
