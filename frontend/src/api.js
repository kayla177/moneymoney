// Thin wrapper around the backend JSON API. All paths are same-origin (/api/...),
// which works in dev via the Vite proxy and in production via FastAPI serving the build.

async function request(path, options) {
  const resp = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    throw new Error(`API ${path} failed: ${resp.status}`);
  }
  return resp.json();
}

export const api = {
  getCategories: () => request("/categories"),

  getTransactions: ({ month, status } = {}) => {
    const params = new URLSearchParams();
    if (month) params.set("month", month);
    if (status) params.set("status", status);
    const qs = params.toString();
    return request(`/transactions${qs ? `?${qs}` : ""}`);
  },

  createTransaction: (body) =>
    request("/transactions", { method: "POST", body: JSON.stringify(body) }),

  updateTransaction: (id, body) =>
    request(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  getAnalysis: (month) => request(`/analysis?month=${month}`),

  // Image import uses multipart/form-data so we don't go through `request`
  // (which would force a JSON content-type and break the boundary).
  importFromImage: async (file) => {
    const formData = new FormData();
    formData.append("image", file);
    const resp = await fetch("/api/transactions/from-image", {
      method: "POST",
      body: formData,
    });
    if (!resp.ok) {
      // The backend includes a useful "detail" string for 5xx errors.
      let detail = `HTTP ${resp.status}`;
      try {
        const body = await resp.json();
        if (body.detail) detail = body.detail;
      } catch (_) { /* keep status */ }
      throw new Error(detail);
    }
    return resp.json();
  },
};

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

// Money is always displayed with the gold-coin prefix (Stardew Valley theme).
// Currency code is accepted for API compatibility but not shown — all current
// transactions are CAD; if multi-currency ever matters we'll surface it explicitly.
export function formatMoney(amount, _currency = "CAD") {
  const formatted = new Intl.NumberFormat("en-CA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(amount || 0));
  return `⛁ ${formatted}`;
}
