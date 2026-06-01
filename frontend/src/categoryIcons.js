// Maps top-level category name → emoji. Used wherever a category is rendered:
// CategoryPicker chips, Transactions list, Analysis legend.
export const CATEGORY_ICON = {
  Food: '🍳',
  Transport: '🚗',
  Shopping: '🛍️',
  Bills: '📜',
  Entertainment: '🎮',
  Health: '🌿',
  Housing: '🏡',
  Transfers: '💌',
  Other: '❓',
};

export const iconFor = (name) => CATEGORY_ICON[name] ?? '❓';
