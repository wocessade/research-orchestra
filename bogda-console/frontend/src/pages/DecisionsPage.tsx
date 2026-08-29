import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
  const [rationale, setRationale] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const snapshot = decisions.data?.data;
  const items = useMemo(() => uniqueDecisions(snapshot?.items ?? []), [snapshot?.items]);
  const projects = useMemo(() => Array.from(new Set(items.map((item) => item.projectId))).sort(), [items]);
  const risks = useMemo(() => Array.from(new Set(items.map((item) => item.risk))).sort(), [items]);
  const filtered = useMemo(
    () => items.filter((item) => (project === "全部" || item.projectId === project) && (risk === "全部" || item.risk === risk)),
    [items, project, risk],
  );
  const canResolve = capabilities.data?.data?.canResolveModelDecision !== false;

  const mutation = useMutation({
    mutationFn: async () => {
      if (!selected || !selectedAction) throw new Error("no decision selected");
      if (selectedAction.requiresRationale && !rationale.trim()) {
        setFormError("请填写操作理由，说明你为何作出这个判断。");
        throw new Error("rationale required");
      }
      setFormError(null);
      return api.command<{ command: string; resourceId: string; acceptedAt: string; snapshot: DecisionCenterSnapshot }>(
        "/api/v1/decisions/" + selected.decisionId,
        { actionId: selectedAction.actionId, expectedRevision: selected.revision, rationale: rationale.trim() || null },
      );
    },
    onSuccess: (response) => {
      queryClient.setQueryData(["decisions"], { ...decisions.data, data: response.data?.snapshot ?? response.data });
      setSelected(null);
      setSelectedAction(null);
      setRationale("");
      setConflict(false);
    },
    onError: (error) => {
      if (!(error instanceof ApiClientError)) return;
      const apiError = error.errors[0];
      const current = apiError?.details?.currentResource as DecisionCenterSnapshot | undefined;
      if (apiError?.code !== "RESOURCE_CHANGED" || !current) return;
      queryClient.setQueryData(["decisions"], { ...decisions.data, data: current });
      const currentItem = current.items.find((item) => item.decisionId === selected?.decisionId);
      if (currentItem) {
        setSelected(currentItem);
        setSelectedAction(currentItem.actions.find((action) => action.actionId === selectedAction?.actionId) ?? currentItem.actions[0] ?? null);
      }
      setConflict(true);
    },
  });

  if (decisions.isPending) return <section className="page"><QueryLoading /></section>;
  if (decisions.isError || !snapshot) return <section className="page"><QueryFailure title="决策来源暂不可用" /></section>;

  function openDecision(item: DecisionItem) {
    setSelected(item);
    setSelectedAction(item.actions[0] ?? null);
    setRationale("");
    setFormError(null);
    setConflict(false);
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
            {groupItems.length === 0 ? <p className="decision-group__empty">这一段目前没有事项。</p> : <div className="decision-group__items">{groupItems.map((item) => <article className="decision-record" key={item.decisionId}>
              <div className="decision-record__rail" aria-hidden="true" /><div className="decision-record__body">
                <div className="decision-record__heading"><div><p className="decision-record__meta">{item.projectId} · {item.risk} 风险 · 修订 {item.revision}</p><h3>{item.title}</h3></div><span className="decision-cost">¥{item.estimatedCost}</span></div>
                <p>{item.reason}</p>
                <div className="evidence-chips">{item.evidence.map((reference) => reference.uri ? <a className="evidence-chip" href={reference.uri} key={reference.kind + ":" + reference.refId}>{reference.label}</a> : <span className="evidence-chip" key={reference.kind + ":" + reference.refId}>{reference.label}</span>)}</div>
                {item.deadline && <time className="decision-deadline" dateTime={item.deadline}>截止 {formatDeadline(item.deadline)}</time>}
                <button type="button" className="text-action decision-open" onClick={() => openDecision(item)} aria-label={"查看：" + item.title}>查看判断细节 ↗</button>
              </div>
            </article>)}</div>}
          </section>;
        })}
      </div>
      {filtered.length === 0 && <div className="empty-state decision-empty"><strong>当前没有待处理决策</strong><span>新的判断会从权威来源进入这里；来源故障时不会伪造空列表。</span></div>}

      <ModalDialog open={Boolean(selected && selectedAction)} title={selected?.title ?? "确认决策"} onClose={() => setSelected(null)} busy={mutation.isPending} footer={<><button type="button" className="secondary-action" data-autofocus onClick={() => setSelected(null)} disabled={mutation.isPending}>返回</button><button type="button" className="primary-action" onClick={() => mutation.mutate()} disabled={!canResolve || mutation.isPending || Boolean(selectedAction?.requiresRationale && !rationale.trim())}>{mutation.isPending ? "等待权威回执…" : selectedAction?.label ?? "确认操作"}</button></>}>
        {selected && selectedAction && <div className="decision-dialog">
          {conflict && <div className="command-conflict" role="alert"><strong>决策已被其他操作修改，请重新确认。</strong><span>已载入当前权威版本；你的操作理由保留，但不会自动重放。</span></div>}
          <p>{selected.reason}</p>
          <dl className="dialog-facts"><div><dt>费用影响</dt><dd>{selectedAction.costImpact}</dd></div><div><dt>质量影响</dt><dd>{selectedAction.qualityImpact ?? "未声明"}</dd></div><div><dt>风险</dt><dd>{selected.risk}</dd></div><div><dt>不可逆后果</dt><dd>{selectedAction.irreversibleConsequence ?? "未声明"}</dd></div></dl>
          <section><h3>证据</h3><div className="evidence-chips">{selected.evidence.map((reference) => reference.uri ? <a className="evidence-chip" href={reference.uri} key={reference.kind + ":" + reference.refId}>{reference.label}</a> : <span className="evidence-chip" key={reference.kind + ":" + reference.refId}>{reference.label}</span>)}</div></section>
          <section><h3>精确日志摘要</h3><p className="log-summary">{selected.logSummary}</p></section>
          {selected.risk.toLowerCase() === "high" && <p className="decision-high-risk">高风险操作需要明确确认。</p>}
          {selectedAction.requiresRationale && <label className="decision-rationale">操作理由<textarea aria-label="操作理由" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="说明这次判断的依据" rows={3} required /></label>}
          {formError && <p className="command-error" role="alert">{formError}</p>}
          {!canResolve && <p className="readonly-note">当前 profile 为 {capabilities.data?.data?.profile ?? "readonly"}，只读，不能处理决策。</p>}
        </div>}
      </ModalDialog>
    </section>
  );
}
