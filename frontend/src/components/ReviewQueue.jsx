import { useEffect, useState } from "react";
import { api, formatMoney } from "../api.js";
import CategoryPicker from "./CategoryPicker.jsx";

// The review queue: transactions the parser captured but couldn't confidently categorize.
// Categorizing one (optionally "learn" so the merchant sticks) removes it from the queue.
export default function ReviewQueue({ categories, onChange }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api
      .getTransactions({ status: "needs_review" })
      .then(setItems)
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const confirm = async (txn, categoryId, subId, learn) => {
    await api.updateTransaction(txn.id, {
      category_id: categoryId,
      subcategory_id: subId,
      learn,
    });
    load();
    onChange?.();
  };

  if (loading) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h1>Review</h1>
      <p className="muted">Transactions waiting for a category.</p>
      {items.length === 0 && (
        <div className="empty">🎉 Nothing to review — you're all caught up.</div>
      )}
      {items.map((txn) => (
        <ReviewCard key={txn.id} txn={txn} categories={categories} onConfirm={confirm} />
      ))}
    </div>
  );
}

function ReviewCard({ txn, categories, onConfirm }) {
  const [cat, setCat] = useState(null);
  const [sub, setSub] = useState(null);
  const [learn, setLearn] = useState(true);

  return (
    <div className="card">
      <div className="row">
        <span className="merchant">{txn.raw_merchant || "(no merchant)"}</span>
        <span className="amount">{formatMoney(txn.amount, txn.currency)}</span>
      </div>
      <div className="row">
        <span className="muted">{new Date(txn.date).toLocaleDateString()}</span>
        <span className="tag">{txn.source}</span>
      </div>

      <CategoryPicker
        categories={categories}
        selectedCategory={cat}
        selectedSub={sub}
        onPick={(c, s) => {
          setCat(c);
          setSub(s);
        }}
      />

      <div className="row" style={{ marginTop: 12 }}>
        <label className="muted">
          <input
            type="checkbox"
            checked={learn}
            onChange={(e) => setLearn(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          Remember this merchant
        </label>
        <button
          className="primary"
          disabled={!cat}
          onClick={() => onConfirm(txn, cat, sub, learn)}
        >
          Save
        </button>
      </div>
    </div>
  );
}
