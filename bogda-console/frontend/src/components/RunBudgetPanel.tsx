import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api, ApiClientError } from "../api/client";
import type { Schemas } from "../api/types";
import { EnvelopeErrors, QueryLoading, SourceStrip } from "./EnvelopeState";

type ModelBudgetSnapshot = Schemas["ModelBudgetSnapshot"];

const stateCopy: Record<ModelBudgetSnapshot["state"], { label: string; recovery: string }> = {
  ready: { label: "预算可用", recovery: "当前预算状态可继续" },
  stale: { label: "快照已过期", recovery: "请回到决策中心重新确认" },
  insufficient: { label: "余额不足", recovery: "余额恢复后再继续" },
  "scheduled-off-peak": { label: "已安排低峰时段", recovery: "等待计划开始" },
  "awaiting-approval": { label: "等待批准", recovery: "前往决策中心" },
  "usage-unknown": { label: "用量未知", recovery: "等待权威用量恢复" },
};

const artifactKinds = new Set(["prompt", "stdout", "stderr", "receipt", "log"]);

function absoluteTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function serverMoney(value: string, currency: string) {
  return `${value} ${currency}`;
}

function statusCopy(snapshot: ModelBudgetSnapshot) {
  const copy = stateCopy[snapshot.state];
  return snapshot.recoveryConditions.length ? snapshot.recoveryConditions : [copy.recovery];
}

export function RunBudgetPanel({ runId }: { runId: string }) {
  const query = useQuery({
    queryKey: ["run-model-budget", runId],
    queryFn: () => api.get<ModelBudgetSnapshot>(`/api/v1/runs/${runId}/model-budget`),
    enabled: Boolean(runId),
  });

  if (query.isPending) return <section className="detail-section run-budget-panel" aria-labelledby="run-budget-title"><QueryLoading /></section>;

  if (query.isError || !query.data?.data) {
    const status = query.error instanceof ApiClientError ? query.error.status : undefined;
    return <section className="detail-section run-budget-panel" aria-labelledby="run-budget-title">
      <div className="detail-heading"><div><p className="page-kicker">MODEL BUDGET / UNAVAILABLE</p><h2 id="run-budget-title">运行预算暂不可用</h2></div><p>{status === 404 ? "没有找到该运行的预算审计快照。" : "保留当前判断，不以空数据替代来源故障。"}</p></div>
      {query.data?.sources && <SourceStrip sources={query.data.sources} />}
      {query.error instanceof ApiClientError && <p className="run-budget-error-detail">{query.error.errors[0]?.message ?? `HTTP ${status ?? "unknown"}`}</p>}
    </section>;
  }

  const envelope = query.data;
  const snapshot = envelope.data;
  if (!snapshot) return null;
  const state = stateCopy[snapshot.state];
  const staleSource = Object.values(envelope.sources).some((source) => source.freshness !== "fresh");
  const artifacts = snapshot.artifacts.filter((artifact) => artifactKinds.has(artifact.kind));

  return <section className="detail-section run-budget-panel" aria-labelledby="run-budget-title">
    <div className="detail-heading"><div><p className="page-kicker">MODEL BUDGET / AUDIT</p><h2 id="run-budget-title">模型预算审计</h2></div><p>服务端快照 revision {snapshot.revision}；此处只读展示，不复制定价或决策状态。</p></div>
    <SourceStrip sources={envelope.sources} />
    <EnvelopeErrors errors={envelope.errors} />
    {staleSource && <p className="run-budget-source-warning" role="status">预算来源陈旧；以下内容保留为已观测快照，不代表当前余额。</p>}
    <div className={`run-budget-status run-budget-status--${snapshot.state}`}>
      <strong>{state.label}</strong><span>{statusCopy(snapshot).join("；")}</span>
    </div>
    <dl className="run-budget-ledger">
      <div><dt>请求 tier</dt><dd>{snapshot.requestedModelTier}</dd></div>
      <div><dt>有效 tier</dt><dd>{snapshot.effectiveModelTier ?? "未知"}</dd></div>
      <div><dt>意图</dt><dd>{snapshot.intent}</dd></div>
      <div><dt>自主模式</dt><dd>{snapshot.effectiveAutonomyMode}</dd></div>
      <div><dt>授权上限</dt><dd>{serverMoney(snapshot.authorizedCeiling, snapshot.currency)}</dd></div>
      <div><dt>已使用</dt><dd>{serverMoney(snapshot.usedCost, snapshot.currency)}</dd></div>
      <div><dt>已预留</dt><dd>{serverMoney(snapshot.reservedCost, snapshot.currency)}</dd></div>
      <div><dt>剩余</dt><dd>{serverMoney(snapshot.remainingCost, snapshot.currency)}</dd></div>
      <div><dt>预计成本</dt><dd>{serverMoney(snapshot.expectedCost, snapshot.currency)}</dd></div>
      <div><dt>价格窗口</dt><dd>{snapshot.pricePeriod}</dd></div>
      <div><dt>计划开始</dt><dd>{absoluteTime(snapshot.scheduledStart)}</dd></div>
      <div><dt>暂停原因</dt><dd>{snapshot.pauseReason ?? "—"}</dd></div>
    </dl>
    <div className="run-budget-recovery" aria-label="恢复条件"><p className="page-kicker">RECOVERY / ONE CALL OUT</p><strong>恢复条件</strong><ul>{statusCopy(snapshot).map((condition) => <li key={condition}>{condition}</li>)}</ul>{snapshot.decisionId && <Link className="text-action" to={`/decisions#${snapshot.decisionId}`}>前往决策中心 · {snapshot.decisionId}</Link>}</div>
    <div className="run-budget-audit-columns">
      <section aria-labelledby="run-budget-events-title"><div className="detail-heading"><h3 id="run-budget-events-title">结构化事件</h3><span>仅摘要</span></div>{snapshot.events.length ? <ol className="run-budget-events">{snapshot.events.map((event) => <li key={event.eventId}><time dateTime={event.occurredAt}>{absoluteTime(event.occurredAt)}</time><strong>{event.eventType}</strong><span>{event.summary ?? "—"}</span></li>)}</ol> : <p className="muted">暂无结构化事件。</p>}</section>
      <section aria-labelledby="run-budget-artifacts-title"><div className="detail-heading"><h3 id="run-budget-artifacts-title">审计引用</h3><span>metadata only</span></div>{artifacts.length ? <ul className="run-budget-artifacts">{artifacts.map((artifact) => <li key={artifact.artifactId}><span>{artifact.kind}</span><a href={artifact.uri}>{artifact.artifactId}</a></li>)}</ul> : <p className="muted">暂无允许展示的元数据引用。</p>}</section>
    </div>
    <section className="run-budget-safety" aria-labelledby="run-budget-safety-title"><h3 id="run-budget-safety-title">系统不变量说明</h3><p>以下是产品固定安全规则，不是该 run 的动态服务端值，也不能在此修改。</p><ul><li>预算增加需批准。</li><li>未知用量采用 fail-closed 恢复门槛。</li><li>结构化事件日志与秘密内容脱敏规则保持启用。</li></ul></section>
  </section>;
}
