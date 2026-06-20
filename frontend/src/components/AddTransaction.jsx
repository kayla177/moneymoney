import { useRef, useState } from "react";
import { api } from "../api.js";
import CategoryPicker from "./CategoryPicker.jsx";

// Two ways to add transactions:
// 1) Screenshot import — upload a statement screenshot, GPT-4o extracts each line.
// 2) Manual entry — for cash purchases or charges under the bank's alert threshold.
function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function AddTransaction({ categories, onAdded, onCreateCategory }) {
  // ---- image-import state ----
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importError, setImportError] = useState(null);
  const fileInputRef = useRef(null);

  // ---- manual-entry state ----
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

  const processImage = async () => {
    if (!file) return;
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await api.importFromImage(file);
      setImportResult(result);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      onAdded?.();
    } catch (e) {
      setImportError(e.message);
    } finally {
      setImporting(false);
    }
  };

  const valid = amount && Number(amount) > 0;

  return (
    <div>
      <h1>Add</h1>

      <div className="card">
        <label className="muted">📷 From screenshot</label>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setImportResult(null);
            setImportError(null);
          }}
          style={{ width: "100%", marginTop: 8, marginBottom: 8 }}
        />
        {file && (
          <p className="muted">
            {file.name} · {Math.round(file.size / 1024)} KB
          </p>
        )}
        <button
          className="primary"
          disabled={!file || importing}
          onClick={processImage}
          style={{ width: "100%", marginTop: 8 }}
        >
          {importing ? "PROCESSING…" : "PROCESS"}
        </button>
        {importResult && (
          <p className="muted" style={{ marginTop: 10 }}>
            ✓ Imported {importResult.imported}
            {importResult.skipped_duplicates > 0 &&
              ` · skipped ${importResult.skipped_duplicates} dupes`}
            {importResult.needs_review > 0 &&
              ` · ${importResult.needs_review} need review`}
          </p>
        )}
        {importError && (
          <p style={{ marginTop: 10, color: "var(--danger)", fontSize: 8 }}>
            ✗ {importError}
          </p>
        )}
      </div>

      <p
        className="muted"
        style={{ textAlign: "center", margin: "18px 4px" }}
      >
        — or add manually —
      </p>

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
          onCreateCategory={onCreateCategory}
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

        <button
          className="primary"
          disabled={!valid}
          onClick={save}
          style={{ width: "100%" }}
        >
          {saved ? "✓ SAVED" : "SAVE"}
        </button>
      </div>
    </div>
  );
}
