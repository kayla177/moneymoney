import { useState } from "react";
import { iconFor } from "../categoryIcons.js";

// Two-step picker: choose a category (chips), then a subcategory (chips).
// Calls onPick(categoryId, subcategoryId) once a category is chosen; subcategory optional.
//
// When `onCreateCategory` is supplied, a "+ CUSTOM" chip lets you type your own
// category name instead of using the generic "Other" bucket. It creates a real,
// reusable category (so it shows up on its own in Analysis) and selects it.
export default function CategoryPicker({
  categories,
  selectedCategory,
  selectedSub,
  onPick,
  onCreateCategory,
}) {
  const active = categories.find((c) => c.id === selectedCategory);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submitCustom = async () => {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      const cat = await onCreateCategory(trimmed);
      onPick(cat.id, null);
      setName("");
      setAdding(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="chips">
        {categories.map((c) => (
          <button
            key={c.id}
            className={`chip ${selectedCategory === c.id ? "selected" : ""}`}
            onClick={() => onPick(c.id, null)}
          >
            {iconFor(c.name)} {c.name.toUpperCase()}
          </button>
        ))}
        {onCreateCategory && (
          <button
            className={`chip ${adding ? "selected" : ""}`}
            onClick={() => setAdding((v) => !v)}
          >
            ✏️ CUSTOM
          </button>
        )}
      </div>

      {adding && onCreateCategory && (
        <div className="row" style={{ marginTop: 8 }}>
          <input
            placeholder="Type a category…"
            value={name}
            autoFocus
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitCustom()}
            style={{ flex: 1 }}
          />
          <button
            className="primary"
            disabled={!name.trim() || busy}
            onClick={submitCustom}
          >
            ADD
          </button>
        </div>
      )}

      {active && active.subcategories.length > 0 && (
        <div className="chips">
          {active.subcategories.map((s) => (
            <button
              key={s.id}
              className={`chip ${selectedSub === s.id ? "selected" : ""}`}
              onClick={() => onPick(active.id, s.id)}
            >
              {s.name.toUpperCase()}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
