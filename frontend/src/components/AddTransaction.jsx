import { useState } from "react";
import { api } from "../api.js";
import CategoryPicker from "./CategoryPicker.jsx";

// Quick manual entry — the "fast-manual" capture fallback for cash purchases or card
// charges that fall under the bank's email-alert threshold. A few taps, no app-switching.
function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function AddTransaction({ categories, onAdded }) {
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [date, setDate] = useState(today());
  const [cat, setCat] = useState(null);
  const [sub, setSub] = useState(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);

  const reset = () => {
    setAmount("");
    setMerchant("");
    setDate(today());
    setCat(null);
    setSub(null);
    setNote("");
  };

  const save = async () => {
    await api.createTransaction({
      date: `${date}T12:00:00`,
      amount,
      raw_merchant: merchant,
      source: "manual",
      category_id: cat,
      subcategory_id: sub,
      note: note || null,
    });
    reset();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    onAdded?.();
  };

  const valid = amount && Number(amount) > 0;

  return (
    <div>
      <h1>Add</h1>
      <p className="muted">Log a cash or small purchase manually.</p>

      <div className="card">
        <label className="muted">Amount</label>
        <input
          type="number"
          inputMode="decimal"
          placeholder="0.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          style={{ width: "100%", marginBottom: 12 }}
        />

        <label className="muted">Merchant (optional)</label>
        <input
          placeholder="e.g. Corner Store"
          value={merchant}
          onChange={(e) => setMerchant(e.target.value)}
          style={{ width: "100%", marginBottom: 12 }}
        />

        <label className="muted">Date</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ width: "100%", marginBottom: 12 }}
        />

        <label className="muted">Category</label>
        <CategoryPicker
          categories={categories}
          selectedCategory={cat}
          selectedSub={sub}
          onPick={(c, s) => {
            setCat(c);
            setSub(s);
          }}
        />

        <label className="muted" style={{ display: "block", marginTop: 12 }}>
          Note (optional)
        </label>
        <input
          placeholder="What was it for?"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          style={{ width: "100%", marginBottom: 12 }}
        />

        <button className="primary" disabled={!valid} onClick={save} style={{ width: "100%" }}>
          {saved ? "✓ SAVED" : "SAVE"}
        </button>
      </div>
    </div>
  );
}
