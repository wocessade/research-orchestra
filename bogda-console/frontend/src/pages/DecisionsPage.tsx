import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { ApiClientError, api } from "../api/client";
import type { CapabilitySnapshot, DecisionAction, DecisionCenterSnapshot, DecisionItem } from "../api/types";
import { ModalDialog } from "../components/Dialogs";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip } from "../components/EnvelopeState";

const groups = [
  { key: "needs-owner-now", label: "需要我现在处理", note: "不处理，工作会停在这里。" },
  { key: "has-deadline", label: "有截止时间", note: "按截止时间排列，避免错过窗口。" },
  { key: "for-information", label: "仅供知晓", note: "不会阻塞执行，只保留判断上下文。" },
] as const;

type Filter = "全部";

function uniqueDecisions(items: DecisionItem[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.decisionId)) return false;
    seen.add(item.decisionId);
    return true;
  });
}

function formatDeadline(deadline: string | null | undefined) {
  if (!deadline) return null;
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(deadline));
}

export function DecisionsPage() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const decisions = useQuery({
    queryKey: ["decisions"],
    queryFn: () => api.get<DecisionCenterSnapshot>("/api/v1/decisions"),
  });
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities"),
  });
  const [project, setProject] = useState<Filter | string>("全部");
  const [risk, setRisk] = useState<Filter | string>("全部");
  const [selected, setSelected] = useState<DecisionItem | null>(null);
  const [selectedAction, setSelectedAction] = useState<DecisionAction | null>(null);
  const [openedRevision, setOpenedRevision] = useState<number | null>(null);
  const [rationale, setRationale] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [withdrawn, setWithdrawn] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [conflictAcknowledged, setConflictAcknowledged] = useState(false);
  const [actionUnavailable, setActionUnavailable] = useState(false);

  const snapshot = decisions.data?.data;
  const items = useMemo(() => uniqueDecisions(snapshot?.items ?? []), [snapshot?.items]);
  const projects = useMemo(() => Array.from(new Set(items.map((item) => item.projectId))).sort(), [items]);
  const risks = useMemo(() => Array.from(new Set(items.map((item) => item.risk))).sort(), [items]);
  const filtered = useMemo(
    () => items.filter((item) => (project === "全部" || item.projectId === project) && (risk === "全部" || item.risk === risk)),
    [items, project, risk],
  );
  const canResolve = capabilities.data?.data?.canResolveModelDecision === true;

  useEffect(() => {
    if (!location.hash || items.length === 0) return;
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!(target instanceof HTMLElement)) return;
    target.focus();
    target.scrollIntoView({ block: "start" });
  }, [items.length, location.hash]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!selected || !selectedAction) throw new Error("no decision selected");
      if (selectedAction.requiresRationale && !rationale.trim()) {
        setFormError("请填写操作理由，说明你为何作出这个判断。");
        throw new Error("rationale required");
      }
      if (conflict && !conflictAcknowledged) {
        setFormError("请重新检查当前修订和操作后再提交。");
        throw new Error("conflict reconfirmation required");
      }
      setFormError(null);
      return api.command<{ command: string; resourceId: string; acceptedAt: string; snapshot: DecisionCenterSnapshot }>(
        "/api/v1/decisions/" + selected.decisionId,
        { actionId: selectedAction.actionId, expectedRevision: openedRevision ?? snapshot?.revision ?? 0, rationale: rationale.trim() || null },
      );
    },
    onSuccess: (response) => {
      queryClient.setQueryData(["decisions"], { ...decisions.data, data: response.data?.snapshot ?? response.data });
      setSelected(null);
      setSelectedAction(null);
      setRationale("");
      setConflict(false);
      setWithdrawn(false);
      setAcknowledged(false);
      setConflictAcknowledged(false);
      setActionUnavailable(false);
    },
    onError: (error) => {
      const apiError = error instanceof ApiClientError ? error.errors[0] : undefined;
      setFormError(apiError?.message ?? (error instanceof Error ? error.message : "操作未获得权威回执；没有自动重试。"));
      if (!(error instanceof ApiClientError)) return;
      const current = apiError?.details?.currentResource as DecisionCenterSnapshot | undefined;
      if (apiError?.code !== "RESOURCE_CHANGED" || !current) return;
      queryClient.setQueryData(["decisions"], { ...decisions.data, data: current });
      setOpenedRevision(current.revision);
      setAcknowledged(false);
      setConflictAcknowledged(false);
      const currentItem = current.items.find((item) => item.decisionId === selected?.decisionId);
      if (currentItem) {
        setSelected(currentItem);
        const currentAction = currentItem.actions.find((action) => action.actionId === selectedAction?.actionId) ?? null;
        setSelectedAction(currentAction);
        setActionUnavailable(!currentAction);
        setWithdrawn(false);
      } else {
        setSelectedAction(null);
        setActionUnavailable(false);
        setWithdrawn(true);
      }
      setConflict(true);
      setFormError(null);
    },
  });

  if (decisions.isPending) return <section className="page"><QueryLoading /></section>;
  if (decisions.isError || !snapshot) return <section className="page"><QueryFailure title="决策来源暂不可用" /></section>;

  function openDecision(item: DecisionItem) {
    setSelected(item);
    setSelectedAction(item.actions[0] ?? null);
    setOpenedRevision(snapshot?.revision ?? 0);
    setRationale("");
    setFormError(null);
    setConflict(false);
    setWithdrawn(false);
    setAcknowledged(false);
    setConflictAcknowledged(false);
    setActionUnavailable(false);
  }

  return (
    <section className="page decisions-page">
      <header className="page-header page-header--split">
        <div><p className="page-kicker">Owner console / 04</p><h1>决策跑道</h1><p className="lede">所有待判断事项只从一个权威列表进入；每次操作都带着打开时的修订号提交。</p></div>
        <div className="decision-count"><strong>{filtered.length}</strong><span>项待判断</span></div>
      </header>
      <SourceStrip sources={decisions.data.sources} />
      <EnvelopeErrors errors={decisions.data.errors} />
      {(decisions.data.errors.length > 0 || Object.values(decisions.data.sources).some((source) => source.freshness !== "fresh")) && <p className="decision-degraded" role="status">来源数据已降级，未用空数据替代权威状态。</p>}

      <div className="filter-bar decision-filters" aria-label="决策筛选">
        <label>项目<select aria-label="项目" value={project} onChange={(event) => setProject(event.target.value)}><option value="全部">全部项目</option>{projects.map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
        <label>风险<select aria-label="风险" value={risk} onChange={(event) => setRisk(event.target.value)}><option value="全部">全部风险</option>{risks.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      </div>

      <div className="decision-runway">
        {groups.map((group, index) => {
          const groupItems = filtered.filter((item) => item.urgencyGroup === group.key).sort((a, b) => (a.deadline ?? "9999").localeCompare(b.deadline ?? "9999"));
          return <section className={"decision-group decision-group--" + group.key} key={group.key} aria-labelledby={"decision-group-" + group.key}>
            <header className="decision-group__heading"><div><p className="page-kicker">Runway / {String(index + 1).padStart(2, "0")}</p><h2 id={"decision-group-" + group.key}>{group.label}</h2></div><span>{groupItems.length} 项 · {group.note}</span></header>
            {groupItems.length === 0 ? <p className="decision-group__empty">这一段目前没有事项。</p> : <div className="decision-group__items">{groupItems.map((item) => <article className="decision-record" id={item.decisionId} data-testid={`decision-item-${item.decisionId}`} tabIndex={-1} key={item.decisionId}>
              <div className="decision-record__rail" aria-hidden="true" /><div className="decision-record__body">
                <div className="decision-record__heading"><div><p className="decision-record__meta">{item.projectId} · {item.risk} 风险 · 条目版本 {item.revision}</p><h3>{item.title}</h3></div><span className="decision-cost">¥{item.estimatedCost}</span></div>
                <p>{item.reason}</p>
                <div className="evidence-chips">{item.evidence.map((reference) => reference.uri ? <a className="evidence-chip" href={reference.uri} key={reference.kind + ":" + reference.refId}>{reference.label}</a> : <span className="evidence-chip" key={reference.kind + ":" + reference.refId}>{reference.label}</span>)}</div>
                {item.deadline && <time className="decision-deadline" dateTime={item.deadline}>截止 {formatDeadline(item.deadline)}</time>}
                <button type="button" className="text-action decision-open" onClick={() => openDecision(item)} aria-label={"查看：" + item.title}>查看判断细节 ↗</button>
              </div>
            </article>)}</div>}
          </section>;
        })}
      </div>
      {items.length === 0 && <div className="empty-state decision-empty"><strong>当前没有待处理决策</strong><span>新的判断会从权威来源进入这里；来源故障时不会伪造空列表。</span></div>}
      {items.length > 0 && filtered.length === 0 && <div className="empty-state decision-empty"><strong>没有匹配的决策</strong><span>权威列表仍有 {items.length} 项，请调整筛选条件。</span><button type="button" className="secondary-action" onClick={() => { setProject("全部"); setRisk("全部"); }}>清除筛选</button></div>}

      <ModalDialog open={Boolean(selected)} title={selected?.title ?? "确认决策"} onClose={() => setSelected(null)} busy={mutation.isPending} footer={<><button type="button" className="secondary-action" data-autofocus onClick={() => setSelected(null)} disabled={mutation.isPending}>返回</button><button type="button" className="primary-action" onClick={() => mutation.mutate()} disabled={withdrawn || actionUnavailable || !selectedAction || !canResolve || mutation.isPending || Boolean(conflict && !conflictAcknowledged) || Boolean(selectedAction?.requiresRationale && !rationale.trim()) || Boolean(selectedAction?.requiresConfirmation && !acknowledged)}>{mutation.isPending ? "等待权威回执…" : withdrawn ? "该决策已处理" : actionUnavailable ? "选择当前操作" : selectedAction?.label ?? "选择当前操作"}</button></>}>
        {selected && <div className="decision-dialog">
          {conflict && <div className="command-conflict" role="alert"><strong>决策已被其他操作修改，请重新确认。</strong><span>已载入当前权威版本；你的操作理由保留，但不会自动重放。</span></div>}
          {withdrawn && <div className="command-conflict" role="alert"><strong>该决策已被处理或撤回，请关闭此窗口。</strong><span>当前权威列表中已找不到它；你的操作理由保留，但不会自动重放。</span></div>}
          {actionUnavailable && <div className="command-conflict" role="alert"><strong>原操作已不在当前权威选项中，请选择一个当前操作。</strong><span>旧操作不会被隐式替换，也不会自动重放。</span></div>}
          <p className="decision-revision"><span>权威列表修订 {openedRevision ?? snapshot.revision}</span> · 条目版本 {selected.revision}</p>
          <p>{selected.reason}</p>
          {!withdrawn && selected.actions.length > 0 && <label className="decision-action-picker">选择操作<select aria-label="选择操作" value={selectedAction?.actionId ?? ""} onChange={(event) => { const next = selected.actions.find((action) => action.actionId === event.target.value); if (next) { setSelectedAction(next); setRationale(""); setAcknowledged(false); setConflictAcknowledged(false); setActionUnavailable(false); setFormError(null); } }}>{selectedAction === null && <option value="" disabled>请选择当前操作</option>}{selected.actions.map((action) => <option key={action.actionId} value={action.actionId}>{action.label}</option>)}</select></label>}
          {selectedAction && <dl className="dialog-facts"><div><dt>费用影响</dt><dd>{selectedAction.costImpact}</dd></div><div><dt>质量影响</dt><dd>{selectedAction.qualityImpact ?? "未声明"}</dd></div><div><dt>风险</dt><dd>{selected.risk}</dd></div><div><dt>不可逆后果</dt><dd>{selectedAction.irreversibleConsequence ?? "未声明"}</dd></div></dl>}
          <section><h3>证据</h3><div className="evidence-chips">{selected.evidence.map((reference) => reference.uri ? <a className="evidence-chip" href={reference.uri} key={reference.kind + ":" + reference.refId}>{reference.label}</a> : <span className="evidence-chip" key={reference.kind + ":" + reference.refId}>{reference.label}</span>)}</div></section>
          <section><h3>精确日志摘要</h3><p className="log-summary">{selected.logSummary}</p></section>
          {selected.risk.toLowerCase() === "high" && <p className="decision-high-risk">高风险操作需要明确确认。</p>}
          {withdrawn ? <div className="decision-rationale-readonly"><strong>已保留的操作理由</strong><p>{rationale || "未填写操作理由。"}</p></div> : (actionUnavailable || selectedAction?.requiresRationale) && <label className="decision-rationale">操作理由<textarea aria-label="操作理由" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="说明这次判断的依据" rows={3} required={Boolean(selectedAction?.requiresRationale)} /></label>}
          {selectedAction?.requiresConfirmation && <label className="decision-acknowledgement"><input aria-label="确认不可逆后果" type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />确认我已理解不可逆后果：{selectedAction.irreversibleConsequence ?? "该操作可能产生不可撤销影响。"}</label>}
          {conflict && !withdrawn && selectedAction && <label className="decision-acknowledgement"><input aria-label="我已重新检查当前修订和操作" type="checkbox" checked={conflictAcknowledged} onChange={(event) => setConflictAcknowledged(event.target.checked)} />我已重新检查当前修订和操作</label>}
          {formError && <p className="command-error" role="alert">{formError}</p>}
          {!canResolve && <p className="readonly-note">{capabilities.isPending ? "正在确认操作能力，所有变更操作已停用。" : capabilities.isError || !capabilities.data?.data ? "当前无法确认操作能力，所有变更操作已停用。" : "当前 profile 为 " + (capabilities.data.data.profile ?? "readonly") + "，只读，不能处理决策。"}</p>}
        </div>}
      </ModalDialog>
    </section>
  );
}
