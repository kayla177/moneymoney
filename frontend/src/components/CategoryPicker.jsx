// Two-step picker: choose a category (chips), then a subcategory (chips).
// Calls onPick(categoryId, subcategoryId) once a category is chosen; subcategory optional.
export default function CategoryPicker({ categories, selectedCategory, selectedSub, onPick }) {
  const active = categories.find((c) => c.id === selectedCategory);
  return (
    <div>
      <div className="chips">
        {categories.map((c) => (
          <button
            key={c.id}
            className={`chip ${selectedCategory === c.id ? "selected" : ""}`}
            onClick={() => onPick(c.id, null)}
          >
            {c.name}
          </button>
        ))}
      </div>
      {active && active.subcategories.length > 0 && (
        <div className="chips">
          {active.subcategories.map((s) => (
            <button
              key={s.id}
              className={`chip ${selectedSub === s.id ? "selected" : ""}`}
              onClick={() => onPick(active.id, s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
