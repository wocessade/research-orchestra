import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";


function Placeholder({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return <section className="page"><p className="page-kicker">{eyebrow}</p><h1>{title}</h1><p className="lede">{text}</p></section>;
}

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Placeholder eyebrow="Observatory / 01" title="今天需要你判断的研究" text="执行事实来自 Prefect；科研判断保持独立。" />} />
        <Route path="/runs" element={<Placeholder eyebrow="Ledger / 02" title="运行账簿" text="按 Prefect 原始状态追踪每一次执行。" />} />
        <Route path="/reviews" element={<Placeholder eyebrow="Review / 03" title="科研结果评审" text="评审追加 RunResult 版本，不改写执行历史。" />} />
        <Route path="/infrastructure" element={<Placeholder eyebrow="Field / 04" title="基础设施" text="分开观察 Worker、队列、共享容量与电源模式。" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
