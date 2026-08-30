import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { OverviewSnapshot, PoolSnapshot, RunSummary } from "../api/types";
import { AutonomyPolicyPanel } from "../components/AutonomyPolicyPanel";
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
  const executionAvailable = data.execution != null;
  const scienceAvailable = data.science != null;
  const infrastructureAvailable = data.infrastructure != null;
  const recent = data.execution?.recentRuns ?? [];
  const attention = data.science?.attentionRuns ?? [];
  const active = recent.filter((run) => !run.state.terminal);
  const review = attention.filter((run) => run.scientific?.scientificStatus === "unreviewed");
  const dorm = data.infrastructure?.dormX86;

  return (
    <section className="page overview-page">
      <header className="page-header page-header--split">
        <div><p className="page-kicker">Observatory / 01</p><h1>今天需要你判断的研究</h1><p className="lede">Prefect 决定执行事实，科研结论另判。</p></div>
        <Link className="text-action" to="/runs">打开运行账簿 <span aria-hidden="true">↗</span></Link>
      </header>
      <SourceStrip sources={envelope.sources} />
      <EnvelopeErrors errors={envelope.errors} />
      <AutonomyPolicyPanel />

      <section className="attention-block section-block" aria-labelledby="attention-title">
        <div className="section-heading"><p>01 / ATTENTION</p><h2 id="attention-title">需要判断</h2><span>{scienceAvailable ? `${attention.length} 条` : "—"}</span></div>
        {scienceAvailable ? <RunLedger runs={attention.slice(0, 4)} emptyText="当前没有需要人工判断的结果" /> : <QueryFailure title="科研结果来源暂不可用" />}
      </section>

      <section className="section-block" aria-labelledby="active-title">
        <div className="section-heading"><p>02 / EXECUTION</p><h2 id="active-title">正在执行</h2><span>{executionAvailable ? `${active.length} 条` : "—"}</span></div>
        {executionAvailable ? <RunLedger runs={active.slice(0, 4)} emptyText="当前没有活动运行" /> : <QueryFailure title="运行来源暂不可用" />}
      </section>

      <section className="section-block" aria-labelledby="review-title">
        <div className="section-heading"><p>03 / SCIENCE</p><h2 id="review-title">等待评审</h2><span>{scienceAvailable ? `${review.length} 条` : "—"}</span></div>
        <p className="lede">打开详情再判断，列表不能一键接受或拒绝。</p>
        {scienceAvailable ? <RunLedger runs={review.slice(0, 4)} emptyText="当前没有待评审结果" reviewEntry /> : <QueryFailure title="科研结果来源暂不可用" />}
      </section>

      {infrastructureAvailable || data.power ? (
        <section className="field-band section-block" aria-labelledby="field-title">
          <div className="section-heading"><p>04 / FIELD</p><h2 id="field-title">宿舍机容量与电源</h2></div>
          <div className="field-band__grid">
            {dorm ? (
              <div><small>共享执行容量</small><strong>{`${dorm.activeSlots} / ${dorm.concurrencyLimit ?? "—"}`}</strong><span>dorm-x86 · CPU/GPU 共用</span></div>
            ) : (
              <div><small>共享执行容量</small><strong>{infrastructureAvailable ? "未接入" : "来源不可用"}</strong><span>{infrastructureAvailable ? "宿舍机未接入 Prefect pool" : "Prefect pool 暂不可读取"}</span></div>
            )}
            {data.power ? (
              <div><small>电源模式</small><strong>{data.power.mode}</strong><span>{data.power.agentReachable === true ? "Agent 可达" : "Agent 不可达或未知"}</span></div>
            ) : (
              <div><small>电源模式</small><strong>来源不可用</strong><span>没有可用的电源状态快照</span></div>
            )}
          </div>
        </section>
      ) : (
        <QueryFailure title="基础设施来源暂不可用" />
      )}

      <section className="section-block" aria-labelledby="recent-title">
        <div className="section-heading"><p>05 / RECENT</p><h2 id="recent-title">最近结果</h2><span>{executionAvailable ? `${recent.length} 条` : "—"}</span></div>
        {executionAvailable ? <RunLedger runs={recent.slice(0, 8)} /> : <QueryFailure title="运行来源暂不可用" />}
      </section>
    </section>
  );
}
