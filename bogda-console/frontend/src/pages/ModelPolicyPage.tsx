import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiClientError } from "../api/client";
import type { CapabilitySnapshot, CommandReceipt, Schemas } from "../api/types";
import { ConfirmDialog } from "../components/Dialogs";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip } from "../components/EnvelopeState";

type ModelPolicyPatch = Schemas["ModelPolicyPatch"];
type ModelPolicySnapshot = Schemas["ModelPolicySnapshot"];
const editable: Array<[keyof ModelPolicyPatch, string]> = [
  ["minimumRemaining", "最低剩余预算"], ["workloadSafetyMargin", "工作量安全余量"], ["defaultModelTier", "默认模型层级"],
  ["allowAutoUpgrade", "包内自动升级 Pro"], ["allowFlashDowngrade", "低风险允许 Flash 降级"], ["preferOffPeak", "偏好低峰时段"],
  ["autoResume", "余额恢复后自动继续"], ["criticalNotifications", "关键通知"],
];

export function ModelPolicyPage() {
  const client = useQueryClient();
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities") });
  const cap = capabilities.data?.data;
  const canSet = cap?.canSetModelPolicy === true;
  const policy = useQuery({ queryKey: ["model-policy"], queryFn: () => api.get<ModelPolicySnapshot>("/api/v1/model-policy"), enabled: cap !== undefined });
  const [draft, setDraft] = useState<ModelPolicyPatch>({});
  const [confirm, setConfirm] = useState<"save" | "inherit" | null>(null);
  const [conflict, setConflict] = useState(false);
  const [current, setCurrent] = useState<ModelPolicySnapshot | null>(null);
  const snapshot = current ?? policy.data?.data;
  const mutation = useMutation({ mutationFn: (payload: { patch: ModelPolicyPatch | null; expectedRevision: number }) => api.command<CommandReceipt<ModelPolicySnapshot>>(
    payload.patch === null ? "/api/v1/model-policy/projects/bogda-main" : "/api/v1/model-policy/projects/bogda-main", payload,
  ) });

  if (capabilities.isPending || policy.isPending) return <section className="page"><QueryLoading /></section>;
  if (!snapshot) return <section className="page"><QueryFailure title="模型策略来源暂不可用" /></section>;

  async function save() {
    if (!canSet || !snapshot) return;
    try {
      const response = await mutation.mutateAsync({ patch: confirm === "inherit" ? null : draft, expectedRevision: snapshot.revision });
      if (response.data?.snapshot) { setCurrent(response.data.snapshot); client.setQueryData(["model-policy"], { ...response, data: response.data.snapshot }); }
      setDraft({}); setConfirm(null); setConflict(false);
    } catch (error) {
      if (error instanceof ApiClientError && error.errors[0]?.code === "RESOURCE_CHANGED") {
        const resource = error.errors[0].details?.currentResource as ModelPolicySnapshot | undefined;
        if (resource) setCurrent(resource);
        setConflict(true); setConfirm(null); setDraft({});
      }
    }
  }

  function value(key: keyof ModelPolicySnapshot) { return (draft[key as keyof ModelPolicyPatch] ?? snapshot![key]) as string | boolean; }
  return <section className="page model-policy-page" role="region" aria-labelledby="model-policy-title">
    <header className="page-header page-header--split"><div><p className="page-kicker">Control / 05</p><h1 id="model-policy-title">模型策略</h1><p className="lede">模型层级与预算控制独立于科研自主模式；所有价格与路由仍由服务端决定。</p></div><span className="profile-flag">{cap?.profile ?? "unknown"}</span></header>
    <SourceStrip sources={policy.data?.sources ?? {}} /><EnvelopeErrors errors={policy.data?.errors ?? []} />
    <section className="section-block safety-baselines" aria-labelledby="safety-title"><div className="section-heading"><p>IMMUTABLE / SAFETY</p><h2 id="safety-title">系统安全基线</h2></div><p className="muted"><strong>仅观察，不可关闭</strong>。它们不是项目开关，也不会被本页面覆盖。模型策略不属于科研自主模式。</p><ul className="fact-list">{Object.entries(snapshot.hardSafetyBaselines).map(([key, enabled]) => <li key={key}><span>{key}</span><strong>{enabled ? "已强制" : "需核查"}</strong></li>)}</ul></section>
    <section className="section-block policy-editor" aria-labelledby="policy-title"><div className="section-heading"><p>PROJECT DEFAULTS</p><h2 id="policy-title">项目默认</h2><span>{snapshot.inheritsGlobal ? "继承全局" : "本项目覆盖全局默认"}</span></div><dl className="policy-meta"><div><dt>来源</dt><dd>{snapshot.source === "project" ? "项目覆盖" : "全局默认"}</dd></div><div><dt>修订号</dt><dd>{snapshot.revision}</dd></div><div><dt>PriceCatalog</dt><dd>{snapshot.priceCatalog.status} · {snapshot.priceCatalog.version ?? "—"}</dd></div></dl><div className="policy-fields">{editable.map(([key, label]) => <label key={String(key)}>{label}{key === "defaultModelTier" ? <select aria-label={label} value={String(value(key))} disabled={!canSet} onChange={e => setDraft(d => ({ ...d, [key]: e.target.value as ModelPolicyPatch[typeof key] }))}><option value="auto">Auto</option><option value="flash">Flash</option><option value="pro">Pro</option></select> : typeof snapshot[key as keyof ModelPolicySnapshot] === "boolean" ? <input type="checkbox" aria-label={label} checked={Boolean(value(key))} disabled={!canSet} onChange={e => setDraft(d => ({ ...d, [key]: e.target.checked as ModelPolicyPatch[typeof key] }))} /> : <input aria-label={label} value={String(value(key))} disabled={!canSet} onChange={e => setDraft(d => ({ ...d, [key]: e.target.value as ModelPolicyPatch[typeof key] }))} />}</label>)}</div><div className="policy-actions"><button type="button" className="secondary-action" disabled={!canSet || snapshot.inheritsGlobal} onClick={() => setConfirm("inherit")}>恢复继承全局</button><button type="button" className="primary-action" disabled={!canSet || Object.keys(draft).length === 0} onClick={() => setConfirm("save")}>保存项目默认</button></div>{!canSet && <p className="readonly-note">当前 profile 为 {cap?.profile ?? "unknown"}，只读，不能修改模型策略。</p>}{conflict && <p className="command-notice" role="status">策略已被其他操作修改，请重新确认</p>}</section>
    <ConfirmDialog open={confirm !== null} title={confirm === "inherit" ? "确认恢复继承" : "确认保存模型策略"} confirmLabel={confirm === "inherit" ? "确认恢复继承" : "确认保存"} busy={mutation.isPending} onClose={() => setConfirm(null)} onConfirm={() => void save()}><p>服务端将以当前修订号验证本次变更；冲突后不会自动重放。</p></ConfirmDialog>
  </section>;
}
