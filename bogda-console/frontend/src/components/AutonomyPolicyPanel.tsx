import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiClientError } from "../api/client";
import type {
  AutonomyMode,
  AutonomyPolicySnapshot,
  CapabilitySnapshot,
  CommandReceipt,
} from "../api/types";
import { ConfirmDialog } from "./Dialogs";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip, envelopeHasErrors, envelopeHasNonFreshSources } from "./EnvelopeState";

const MODE_LABELS: Record<AutonomyMode, string> = {
  manual: "手动",
  supervised: "监督执行",
  autonomous: "范围内自主",
};
const MODE_ORDER: AutonomyMode[] = ["manual", "supervised", "autonomous"];

const FUTURE_RUNS_COPY = "只影响之后创建的运行；正在运行和已经创建的任务继续使用其冻结模式。";
const AUTONOMOUS_GUARD_COPY = "科研结论、对外发布、新增支出和超预算实验仍需人工批准。";

type PendingChange =
  | { scope: "global"; mode: AutonomyMode }
  | { scope: "project"; mode: AutonomyMode | null };

function effectiveMode(snapshot: AutonomyPolicySnapshot, projectId: string): AutonomyMode {
  return snapshot.projectOverrides[projectId] ?? snapshot.globalDefault;
}

function ModeBand({
  name,
  ariaLabel,
  value,
  disabled,
  namePrefix,
  onSelect,
}: {
  name: string;
  ariaLabel: string;
  value: AutonomyMode | null;
  disabled: boolean;
  namePrefix?: string;
  onSelect: (mode: AutonomyMode) => void;
}) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="mode-band wrap">
      {MODE_ORDER.map((mode) => {
        const set = value === mode;
        const label = MODE_LABELS[mode];
        return (
          <label
            key={mode}
            className={`mode-detent mode-detent--${mode}${set ? " is-set" : ""}`}
          >
            <input
              type="radio"
              name={name}
              value={mode}
              checked={set}
              disabled={disabled}
              aria-label={namePrefix ? `${namePrefix}${label}` : label}
              onChange={() => onSelect(mode)}
            />
            <span className="mode-detent__tick" aria-hidden="true" />
            <span className="mode-detent__label">{label}</span>
          </label>
        );
      })}
    </div>
  );
}

export function AutonomyPolicyPanel() {
  const queryClient = useQueryClient();
  const capabilitiesQuery = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities"),
  });
  const capabilities = capabilitiesQuery.data?.data;
  const canLoadPolicy = capabilitiesQuery.isSuccess
    && !envelopeHasErrors(capabilitiesQuery.data)
    && capabilities?.canSetAutonomyMode === true;
  const policyQuery = useQuery({
    queryKey: ["autonomy-policy"],
    queryFn: () => api.get<AutonomyPolicySnapshot>("/api/v1/autonomy-policy"),
    enabled: canLoadPolicy,
  });
  const [snapshot, setSnapshot] = useState<AutonomyPolicySnapshot | null>(null);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [latchOpen, setLatchOpen] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const policy = snapshot ?? policyQuery.data?.data;
  const projectId = capabilities?.projectId ?? "bogda-main";
  const projectOverride = policy?.projectOverrides[projectId];
  const covering = Boolean(projectOverride) || latchOpen;
  const effective = policy
    ? effectiveMode(policy, projectId)
    : capabilities?.effectiveAutonomyMode ?? null;
  const canSet = canLoadPolicy
    && policyQuery.isSuccess
    && !envelopeHasErrors(policyQuery.data)
    && !envelopeHasNonFreshSources(policyQuery.data);

  async function confirmChange() {
    if (!pending || !policy) return;
    setBusy(true);
    try {
      const path = pending.scope === "global"
        ? "/api/v1/autonomy-policy/global"
        : `/api/v1/autonomy-policy/projects/${projectId}`;
      const response = await api.command<CommandReceipt<AutonomyPolicySnapshot>>(path, {
        mode: pending.mode,
        expectedRevision: policy.revision,
      });
      if (response.data?.snapshot) {
        setSnapshot(response.data.snapshot);
        queryClient.setQueryData(["autonomy-policy"], { data: response.data.snapshot, sources: {}, errors: [] });
        if (pending.scope === "project" && pending.mode === null) setLatchOpen(false);
      }
      setConflict(false);
      setMutationError(null);
      setPending(null);
    } catch (error) {
      if (error instanceof ApiClientError && error.errors[0]?.code === "RESOURCE_CHANGED") {
        const current = error.errors[0].details?.currentResource as AutonomyPolicySnapshot | undefined;
        if (current) setSnapshot(current);
        setConflict(true);
        setMutationError(null);
        setPending(null);
      } else {
        setMutationError(error instanceof Error ? error.message : "科研自主策略写入失败");
        setPending(null);
      }
    } finally {
      setBusy(false);
    }
  }

  if (capabilitiesQuery.isPending) return null;
  if (capabilitiesQuery.isError || !capabilities) {
    return <section className="section-block autonomy-panel" role="region" aria-labelledby="autonomy-title"><h2 id="autonomy-title">科研自主模式</h2><QueryFailure title="能力来源暂不可用" /></section>;
  }
  if (canLoadPolicy && policyQuery.isPending) {
    return <section className="section-block autonomy-panel"><QueryLoading /></section>;
  }
  if (canLoadPolicy && (policyQuery.isError || !policy)) {
    return <section className="section-block autonomy-panel" role="region" aria-labelledby="autonomy-title"><h2 id="autonomy-title">科研自主模式</h2><QueryFailure title="科研自主策略来源暂不可用" /></section>;
  }

  return (
    <section className="section-block autonomy-panel" role="region" aria-labelledby="autonomy-title">
      <div className="section-heading">
        <p>00 / POLICY</p>
        <h2 id="autonomy-title">科研自主模式</h2>
      </div>
      <SourceStrip sources={policyQuery.data?.sources ?? {}} />
      <EnvelopeErrors errors={policyQuery.data?.errors ?? []} />
      <div className="autonomy-facts">
        <div><small>全局默认</small><strong>{policy ? MODE_LABELS[policy.globalDefault] : "—"}</strong></div>
        <div><small>当前项目</small><strong>{projectId}</strong></div>
        <div><small>项目有效模式</small><strong>{effective ? MODE_LABELS[effective] : "—"}</strong></div>
        <div><small>来源</small><strong>{policy ? (projectOverride ? "项目覆盖" : "全局默认") : "策略后端尚未接入"}</strong></div>
        <div><small>修订号</small><strong>{policy?.revision ?? "—"}</strong></div>
      </div>

      <div className="mode-choice">
        <p>全局默认模式</p>
        <ModeBand
          name="global-autonomy"
          ariaLabel="全局默认模式"
          value={policy?.globalDefault ?? null}
          disabled={!canSet}
          onSelect={(mode) => setPending({ scope: "global", mode })}
        />
      </div>

      <div className="mode-choice">
        <p>项目策略</p>
        <div role="radiogroup" aria-label="项目策略" className="mode-latch">
          <label className={`mode-latch__cell${!covering ? " is-set" : ""}`}>
            <input
              type="radio"
              name="project-latch"
              value="inherit"
              checked={!covering}
              disabled={!canSet}
              onChange={() => {
                if (projectOverride) setPending({ scope: "project", mode: null });
                else setLatchOpen(false);
              }}
            />
            继承全局
          </label>
          <label className={`mode-latch__cell${covering ? " is-set" : ""}`}>
            <input
              type="radio"
              name="project-latch"
              value="override"
              checked={covering}
              disabled={!canSet}
              onChange={() => setLatchOpen(true)}
            />
            本项目覆盖
          </label>
        </div>
        {covering && (
          <ModeBand
            name="project-autonomy"
            ariaLabel="当前项目模式"
            value={projectOverride ?? null}
            disabled={!canSet}
            namePrefix="项目"
            onSelect={(mode) => setPending({ scope: "project", mode })}
          />
        )}
      </div>

      {!canSet && !envelopeHasNonFreshSources(policyQuery.data) && (
        <p className="readonly-note">当前 profile 为 {capabilities?.profile ?? "unknown"}，只读，不能修改科研自主模式。</p>
      )}
      {envelopeHasNonFreshSources(policyQuery.data) && (
        <p className="command-notice" role="status">权威快照不是实时数据；刷新成功前禁止写入。</p>
      )}
      {conflict && <p className="command-notice" role="status">策略已被其他操作修改</p>}
      {mutationError && <p className="command-error" role="alert">{mutationError}</p>}

      <ConfirmDialog
        open={pending !== null}
        title="确认切换科研自主模式"
        confirmLabel="确认切换"
        busy={busy}
        onClose={() => { if (!busy) setPending(null); }}
        onConfirm={() => void confirmChange()}
      >
        <p>{FUTURE_RUNS_COPY}</p>
        {pending?.mode === "autonomous" && <p>{AUTONOMOUS_GUARD_COPY}</p>}
      </ConfirmDialog>
    </section>
  );
}
