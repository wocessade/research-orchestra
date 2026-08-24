import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { OverviewPage } from "../pages/OverviewPage";
import { ReviewsPage } from "../pages/ReviewsPage";
import { RunDetailPage } from "../pages/RunDetailPage";
import { RunsPage } from "../pages/RunsPage";


function Placeholder({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return <section className="page"><p className="page-kicker">{eyebrow}</p><h1>{title}</h1><p className="lede">{text}</p></section>;
}

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/infrastructure" element={<Placeholder eyebrow="Field / 04" title="基础设施" text="分开观察 Worker、队列、共享容量与电源模式。" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
