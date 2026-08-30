import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { CapabilitySnapshot, CommandReceipt, DeploymentSummary, InfrastructureView, Page, PoolSnapshot, QueueSnapshot, RunSummary } from "../api/types";
import { ConfirmDialog } from "../components/Dialogs";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip, envelopeHasErrors } from "../components/EnvelopeState";
import { RunPreparation } from "../components/RunPreparation";

type PendingAction =
  | { kind: "queue"; queue: QueueSnapshot }
  | { kind: "schedule"; deployment: DeploymentSummary; schedule: NonNullable<DeploymentSummary["schedules"]>[number] };

function formatAbsolute(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function PoolLedger({ pool, canPause, onAction }: { pool: PoolSnapshot; canPause: boolean; onAction: (action: PendingAction) => void }) {
  const isDorm = pool.name === "dorm-x86";
  return <article className="pool-ledger">
    <header><div><p className="page-kicker">Work pool</p><h2>{pool.name}</h2></div><span className={`plain-status plain-status--${pool.status.toLowerCase()}`}>{pool.status}</span></header>
    <div className="capacity-line"><strong>{isDorm ? `共享并发 ${pool.activeSlots} / ${pool.concurrencyLimit ?? "—"}` : `并发 ${pool.activeSlots} / ${pool.concurrencyLimit ?? "—"}`}</strong><span>{isDorm ? "CPU 与 GPU 任务共用这一上限" : "Prefect 工作池容量"}</span></div>
    <section aria-labelledby={`${pool.name}-workers`}><h3 id={`${pool.name}-workers`}>Workers</h3>{pool.workers?.length ? <ul className="infra-list">{pool.workers.map((worker) => <li key={worker.workerId}><span><strong>{worker.name}</strong><small>Heartbeat {formatAbsolute(worker.lastHeartbeatTime)}</small></span><em className={`plain-status plain-status--${worker.status.toLowerCase()}`}>{worker.status}</em></li>)}</ul> : <p className="muted">没有 Worker 记录。</p>}</section>
    <section aria-labelledby={`${pool.name}-queues`}><h3 id={`${pool.name}-queues`}>Work queues</h3>{pool.queues?.length ? <ul className="infra-list">{pool.queues.map((queue) => <li key={queue.queueId}><span><strong>{queue.name}</strong><small>{queue.status} · {queue.isPaused ? "已暂停" : "接收运行"}</small></span><button type="button" className="quiet-action" disabled={!canPause} onClick={() => onAction({ kind: "queue", queue })}>{queue.isPaused ? `恢复队列 ${queue.name}` : `暂停队列 ${queue.name}`}</button></li>)}</ul> : <p className="muted">没有队列记录。</p>}</section>
  </article>;
}

type PropertySchema = { type?: string; title?: string; description?: string };
type DeploymentSchema = { properties?: Record<string, PropertySchema>; required?: string[] };

export function coerceDeploymentParameters(values: Record<string, string>, schema?: DeploymentSchema): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [name, property] of Object.entries(schema?.properties ?? {})) {
    const value = values[name] ?? "";
    if (schema?.required?.includes(name) && value === "") throw new Error(`${property.title ?? name} 为必填项`);
    if (value === "") continue;
    if (!property.type || property.type === "string") result[name] = value;
    else if (property.type === "integer") {
      if (!/^-?\d+$/.test(value)) throw new Error(`${property.title ?? name} 必须是整数`);
      result[name] = Number(value);
    } else if (property.type === "number") {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) throw new Error(`${property.title ?? name} 必须是数字`);
      result[name] = parsed;
    } else if (property.type === "boolean") result[name] = value === "true";
    else throw new Error(`${property.title ?? name} 的参数类型暂不支持`);
  }
  return result;
}

export function InfrastructurePage() {
  const queryClient = useQueryClient();
  const infrastructure = useQuery({ queryKey: ["infrastructure"], queryFn: () => api.get<InfrastructureView>("/api/v1/infrastructure") });
  const deployments = useQuery({ queryKey: ["deployments"], queryFn: () => api.get<Page<DeploymentSummary>>("/api/v1/deployments") });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities") });
  const [action, setAction] = useState<PendingAction | null>(null);
  const [selectedDeployment, setSelectedDeployment] = useState<DeploymentSummary | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const cap = capabilities.data?.data;
  const capReady = capabilities.isSuccess && !envelopeHasErrors(capabilities.data);
  const canPauseQueue = capReady && cap?.canPauseWorkQueue === true;
  const canSubmitDeployment = capReady && cap?.canSubmitRegisteredDeployment === true;
  const canPauseSched = capReady && cap?.canPauseSchedule === true;

  const actionMutation = useMutation({ mutationFn: async (pending: PendingAction) => {
    if (pending.kind === "queue") {
      const verb = pending.queue.isPaused ? "resume" : "pause";
      return api.command<CommandReceipt<QueueSnapshot>>(`/api/v1/work-queues/${pending.queue.queueId}/${verb}`, { expectedCommandVersion: pending.queue.commandVersion });
    }
    const verb = pending.schedule.active ? "pause" : "resume";
    return api.command<CommandReceipt<DeploymentSummary>>(`/api/v1/deployments/${pending.deployment.deploymentId}/schedules/${pending.schedule.scheduleId}/${verb}`, { expectedCommandVersion: pending.schedule.commandVersion });
  }});

  const dorm = useMemo(() => infrastructure.data?.data?.pools?.find((pool) => pool.name === "dorm-x86"), [infrastructure.data]);

  async function confirmAction() {
    if (!action) return;
    const response = await actionMutation.mutateAsync(action).catch(() => null);
    if (!response) return;
    if (action.kind === "queue") setNotice(`队列 ${action.queue.name} 已${action.queue.isPaused ? "恢复" : "暂停"}`);
    else setNotice(`日程 ${action.schedule.label} 已${action.schedule.active ? "暂停" : "恢复"}`);
    setAction(null);
    await queryClient.invalidateQueries({ queryKey: ["infrastructure"] });
    await queryClient.invalidateQueries({ queryKey: ["deployments"] });
  }

  if (infrastructure.isPending) return <section className="page"><QueryLoading /></section>;
  if (infrastructure.isError || !infrastructure.data.data) return <section className="page"><QueryFailure title="基础设施来源暂不可用" /></section>;
  const data = infrastructure.data.data;
  const powerMeta = infrastructure.data.sources.power;

  return <section className="page infrastructure-page">
    <header className="page-header page-header--split"><div><p className="page-kicker">Field / 04</p><h1>基础设施</h1><p className="lede">容量、队列和电源各看来源，不互相推断。</p></div><span className="profile-flag">{cap?.profile ?? "读取能力中"}</span></header>
    <SourceStrip sources={infrastructure.data.sources} />
    <EnvelopeErrors errors={infrastructure.data.errors} />
    <SourceStrip sources={capabilities.data?.sources ?? {}} />
    <EnvelopeErrors errors={capabilities.data?.errors ?? []} />
    {dorm && dorm.concurrencyLimit !== 1 && <div className="contract-alert" role="alert"><strong>宿舍机共享并发配置不符合约束</strong><span>期望 1，Prefect 当前报告 {dorm.concurrencyLimit ?? "未设置"}。</span></div>}
    {notice && <div className="command-notice" role="status">{notice}</div>}

    <section className="power-observation" aria-labelledby="power-title"><div><p className="page-kicker">Power agent / mock adapter</p><h2 id="power-title">宿舍机电源状态</h2></div>{data.dormPower ? <div className="power-facts"><strong>{data.dormPower.mode}</strong><span>Agent {data.dormPower.agentReachable === true ? "可达" : data.dormPower.agentReachable === false ? "不可达" : "未知"}</span><span>Sleep inhibition {data.dormPower.sleepInhibited === true ? "开启" : data.dormPower.sleepInhibited === false ? "关闭" : "未知"}</span><time dateTime={data.dormPower.lastTransitionAt ?? undefined}>{formatAbsolute(data.dormPower.lastTransitionAt)}</time>{powerMeta?.sourceMode === "mock" && <em>模拟数据</em>}</div> : <p className="muted">Power Agent 数据不可用。</p>}</section>

    <div className="pool-grid">{data.pools?.map((pool) => <PoolLedger key={pool.name} pool={pool} canPause={canPauseQueue} onAction={setAction} />) ?? <p className="muted">Prefect 工作池数据不可用。</p>}</div>

    <section className="deployment-section section-block" aria-labelledby="deployments-title"><div className="section-heading"><p>Registered</p><h2 id="deployments-title">已注册 Deployments</h2><span>{deployments.data?.data?.items.length ?? "—"} 个</span></div>{deployments.isPending ? <QueryLoading /> : deployments.isError || !deployments.data?.data ? <QueryFailure title="Deployment 来源暂不可用" /> : deployments.data.data.items.map((deployment) => <article className="deployment-record" key={deployment.deploymentId}><div><p className="page-kicker">{deployment.flowName}</p><h3>{deployment.name}</h3><span>{deployment.workPoolName} / {deployment.workQueueName}</span></div><div className="deployment-actions"><button type="button" className="primary-action" disabled={!canSubmitDeployment || !deployment.allowlisted} onClick={() => setSelectedDeployment(deployment)}>提交 {deployment.name}</button></div>{Boolean(deployment.schedules?.length) && <ul className="schedule-list">{deployment.schedules?.map((schedule) => <li key={schedule.scheduleId}><span><strong>{schedule.label}</strong><small>{schedule.active ? "active" : "paused"}</small></span><button type="button" className="quiet-action" disabled={!canPauseSched} onClick={() => setAction({ kind: "schedule", deployment, schedule })}>{schedule.active ? `暂停日程 ${schedule.label}` : `恢复日程 ${schedule.label}`}</button></li>)}</ul>}</article>)}</section>

    <ConfirmDialog open={Boolean(action)} title={action?.kind === "queue" ? `${action.queue.isPaused ? "恢复" : "暂停"}队列 ${action.queue.name}` : `${action?.schedule.active ? "暂停" : "恢复"}日程 ${action?.schedule.label}`} confirmLabel={action?.kind === "queue" ? `确认${action.queue.isPaused ? "恢复" : "暂停"}` : `确认${action?.schedule.active ? "暂停" : "恢复"}`} onClose={() => setAction(null)} onConfirm={confirmAction} busy={actionMutation.isPending}>请求会提交给 Prefect；界面等待回执后才更新。{actionMutation.isError && <span className="command-error" role="alert">操作未获得权威回执；没有自动重试。</span>}</ConfirmDialog>
    <RunPreparation
      deployment={selectedDeployment}
      open={Boolean(selectedDeployment)}
      onClose={() => setSelectedDeployment(null)}
      onSubmitted={(run) => {
        setNotice(`已提交：${run.name}`);
        void queryClient.invalidateQueries({ queryKey: ["runs"] });
      }}
    />
  </section>;
}
