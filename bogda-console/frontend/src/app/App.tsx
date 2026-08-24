import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { OverviewPage } from "../pages/OverviewPage";
import { InfrastructurePage } from "../pages/InfrastructurePage";
import { ReviewsPage } from "../pages/ReviewsPage";
import { RunDetailPage } from "../pages/RunDetailPage";
import { RunsPage } from "../pages/RunsPage";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/reviews" element={<ReviewsPage />} />
        <Route path="/infrastructure" element={<InfrastructurePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
