import { useEffect, useState } from "react";
import { api } from "./api.js";
import ReviewQueue from "./components/ReviewQueue.jsx";
import Transactions from "./components/Transactions.jsx";
import Analysis from "./components/Analysis.jsx";

const TABS = [
  { id: "review", label: "Review" },
  { id: "transactions", label: "Transactions" },
  { id: "analysis", label: "Analysis" },
];

export default function App() {
  const [tab, setTab] = useState("review");
  const [categories, setCategories] = useState([]);
  const [reviewCount, setReviewCount] = useState(0);

  // Categories are needed across screens; load once.
  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => {});
  }, []);

  const refreshReviewCount = () => {
    api
      .getTransactions({ status: "needs_review" })
      .then((txns) => setReviewCount(txns.length))
      .catch(() => {});
  };
  useEffect(refreshReviewCount, []);

  return (
    <div className="app">
      {tab === "review" && (
        <ReviewQueue categories={categories} onChange={refreshReviewCount} />
      )}
      {tab === "transactions" && <Transactions categories={categories} />}
      {tab === "analysis" && <Analysis />}

      <nav className="tabbar">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === "review" && reviewCount > 0 && (
              <span className="badge">{reviewCount}</span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
}
