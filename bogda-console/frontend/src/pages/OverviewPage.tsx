import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { OverviewSnapshot, PoolSnapshot, RunSummary } from "../api/types";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip } from "../components/EnvelopeState";
import { RunLedger } from "../components/RunLedger";

type OverviewData = OverviewSnapshot & {
  execution?: { countsByPrefectType?: Record<string, number>; recentRuns?: RunSummary[] } | null;
  science?: { countsByScientificStatus?: Record<string, number>; attentionRuns?: RunSummary[] } | null;
  infrastructure?: { piService?: PoolSnapshot | null; dormX86?: PoolSnapshot | null } | null;
};

export function OverviewPage() {
  const query = useQuery({ queryKey: ["overview"], queryFn: () => api.get<OverviewData>("/api/v1/overview") });
  if (query.isPending) return <section className="page"><QueryLoading /></section>;
  if (query.isError || !query.data.data) return <section className="page"><QueryFailure title="总览来源暂不可用" /></section>;

  const envelope = query.data;
  const data = envelope.data!;
  const recent = data.execution?.recentRuns ?? [];
  const attention = data.science?.attentionRuns ?? [];
  const active = recent.filter((run) => !run.state.terminal);
  const review = attention.filter((run) => run.scientific?.scientificStatus === "unreviewed");
  const dorm = data.infrastructure?.dormX86;

  return (
    <section className="page overview-page">
      <header className="page-header page-header--split">
        <div><p className="page-kicker">Observatory / 01</p><h1>今天需要你判断的研究</h1><p className="lede">Prefect 决定执行事实，RunResult 承载科研判断。两者不会合并成一个‘成功’。</p></div>
        <Link className="text-action" to="/runs">打开运行账簿 <span aria-hidden="true">↗</span></Link>
      </header>
      <SourceStrip sources={envelope.sources} />
      <EnvelopeErrors errors={envelope.errors} />

      <section className="attention-block section-block" aria-labelledby="attention-title">
        <div className="section-heading"><p>01 / ATTENTION</p><h2 id="attention-title">需要判断</h2><span>{attention.length} 条</span></div>
        <RunLedger runs={attention.slice(0, 4)} emptyText="当前没有需要人工判断的结果" />
      </section>

      <section className="section-block" aria-labelledby="active-title">
        <div className="section-heading"><p>02 / EXECUTION</p><h2 id="active-title">正在执行</h2><span>{active.length} 条</span></div>
        <RunLedger runs={active.slice(0, 4)} emptyText="当前没有活动运行" />
      </section>

      <section className="section-block" aria-labelledby="review-title">
        <div className="section-heading"><p>03 / SCIENCE</p><h2 id="review-title">等待评审</h2><span>{review.length} 条</span></div>
        <RunLedger runs={review.slice(0, 4)} emptyText="当前没有待评审结果" />
      </section>

      <section className="field-band section-block" aria-labelledby="field-title">
        <div className="section-heading"><p>04 / FIELD</p><h2 id="field-title">宿舍机容量与电源</h2></div>
        <div className="field-band__grid">
          <div><small>共享执行容量</small><strong>{dorm ? `${dorm.activeSlots} / ${dorm.concurrencyLimit ?? "—"}` : "来源不可用"}</strong><span>dorm-x86 · CPU/GPU 共用</span></div>
          <div><small>电源模式</small><strong>{data.power?.mode ?? "unknown"}</strong><span>{data.power?.agentReachable === true ? "Agent 可达" : "Agent 不可达或未知"}</span></div>
        </div>
      </section>

      <section className="section-block" aria-labelledby="recent-title">
        <div className="section-heading"><p>05 / RECENT</p><h2 id="recent-title">最近结果</h2><span>{recent.length} 条</span></div>
        <RunLedger runs={recent.slice(0, 8)} />
      </section>
    </section>
  );
}
