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

const MODE_LABELS: Record<AutonomyMode, string> = {
  manual: "手动",
  supervised: "监督执行",
  autonomous: "范围内自主",
};

const FUTURE_RUNS_COPY = "只影响之后创建的运行；正在运行和已经创建的任务继续使用其冻结模式。";
const AUTONOMOUS_GUARD_COPY = "科研结论、对外发布、新增支出和超预算实验仍需人工批准。";

type PendingChange =
  | { scope: "global"; mode: AutonomyMode }
  | { scope: "project"; mode: AutonomyMode | null };

function effectiveMode(snapshot: AutonomyPolicySnapshot, projectId: string): AutonomyMode {
  return snapshot.projectOverrides[projectId] ?? snapshot.globalDefault;
}

export function AutonomyPolicyPanel() {
  const queryClient = useQueryClient();
  const capabilitiesQuery = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities"),
  });
  const capabilities = capabilitiesQuery.data?.data;
  const canSet = capabilities?.canSetAutonomyMode === true;
  const policyQuery = useQuery({
    queryKey: ["autonomy-policy"],
    queryFn: () => api.get<AutonomyPolicySnapshot>("/api/v1/autonomy-policy"),
    enabled: canSet,
  });
  const [snapshot, setSnapshot] = useState<AutonomyPolicySnapshot | null>(null);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState(false);

  const policy = snapshot ?? policyQuery.data?.data;
  const projectId = capabilities?.projectId ?? "bogda-main";
  const projectOverride = policy?.projectOverrides[projectId];
  const effective = policy
    ? effectiveMode(policy, projectId)
    : capabilities?.effectiveAutonomyMode ?? null;

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
      }
      setConflict(false);
      setPending(null);
    } catch (error) {
      if (error instanceof ApiClientError && error.errors[0]?.code === "RESOURCE_CHANGED") {
        const current = error.errors[0].details?.currentResource as AutonomyPolicySnapshot | undefined;
        if (current) setSnapshot(current);
        setConflict(true);
        setPending(null);
      }
    } finally {
      setBusy(false);
    }
  }

  if (capabilitiesQuery.isPending || !capabilities) return null;
  if (canSet && (policyQuery.isPending || !policy)) return null;

  return (
    <section className="section-block autonomy-panel" role="region" aria-labelledby="autonomy-title">
      <div className="section-heading">
        <p>00 / POLICY</p>
        <h2 id="autonomy-title">科研自主模式</h2>
      </div>
      <div className="autonomy-facts">
        <div><small>全局默认</small><strong>{policy ? MODE_LABELS[policy.globalDefault] : "—"}</strong></div>
        <div><small>当前项目</small><strong>{projectId}</strong></div>
        <div><small>项目有效模式</small><strong>{effective ? MODE_LABELS[effective] : "—"}</strong></div>
        <div><small>来源</small><strong>{policy ? (projectOverride ? "项目覆盖" : "全局默认") : "策略后端尚未接入"}</strong></div>
        <div><small>修订号</small><strong>{policy?.revision ?? "—"}</strong></div>
      </div>

      <div className="mode-choice">
        <p>全局默认模式</p>
        <div role="radiogroup" aria-label="全局默认模式" className="mode-choice-row wrap">
          {(Object.keys(MODE_LABELS) as AutonomyMode[]).map((mode) => (
            <label key={`global-${mode}`}>
              <input
                type="radio"
                name="global-autonomy"
                value={mode}
                checked={policy?.globalDefault === mode}
                disabled={!canSet}
                onChange={() => setPending({ scope: "global", mode })}
              />
              {MODE_LABELS[mode]}
            </label>
          ))}
        </div>
      </div>

      <div className="mode-choice">
        <p>当前项目模式</p>
        <div role="radiogroup" aria-label="当前项目模式" className="mode-choice-row wrap">
          <label>
            <input
              type="radio"
              name="project-autonomy"
              value="inherit"
              checked={!projectOverride}
              disabled={!canSet}
              onChange={() => setPending({ scope: "project", mode: null })}
            />
            继承全局
          </label>
          {(Object.keys(MODE_LABELS) as AutonomyMode[]).map((mode) => (
            <label key={`project-${mode}`}>
              <input
                type="radio"
                name="project-autonomy"
                value={mode}
                aria-label={`项目${MODE_LABELS[mode]}`}
                checked={projectOverride === mode}
                disabled={!canSet}
                onChange={() => setPending({ scope: "project", mode })}
              />
              {MODE_LABELS[mode]}
            </label>
          ))}
        </div>
      </div>

      {!canSet && (
        <p className="readonly-note">当前 profile 为 {capabilities?.profile ?? "unknown"}，只读，不能修改科研自主模式。</p>
      )}
      {conflict && <p className="command-notice" role="status">策略已被其他操作修改</p>}

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
