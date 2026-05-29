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
};

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function formatMoney(amount, currency = "CAD") {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
  }).format(Number(amount || 0));
}
