import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiClientError } from "../api/client";
import type { CapabilitySnapshot, CommandReceipt, Envelope, Schemas } from "../api/types";
import { ConfirmDialog } from "../components/Dialogs";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip, envelopeHasNonFreshSources } from "../components/EnvelopeState";

type ModelPolicyPatch = Schemas["ModelPolicyPatch"];
type ModelPolicySnapshot = Schemas["ModelPolicySnapshot"];
type UsageBalanceSnapshot = Schemas["UsageBalanceSnapshot"];
type ConfirmKind = "save" | "inherit";
type PolicyScope = "project" | "global";

const FIELD_COPY: Array<{ key: keyof ModelPolicyPatch; label: string }> = [
  { key: "minimumRemaining", label: "最低剩余预算" },
  { key: "workloadSafetyMargin", label: "工作量安全余量" },
  { key: "defaultModelTier", label: "默认模型层级" },
  { key: "allowAutoUpgrade", label: "包内自动升级 Pro" },
  { key: "allowFlashDowngrade", label: "低风险允许 Flash 降级" },
  { key: "preferOffPeak", label: "偏好低峰时段" },
  { key: "autoResume", label: "余额恢复后自动继续" },
  { key: "criticalNotifications", label: "关键通知" },
];

function envelopeHasErrors(envelope: Envelope<unknown> | undefined) {
  return Boolean(envelope?.errors.length);
}

function PolicyField({
  field,
  snapshot,
  draft,
  disabled,
  onChange,
}: {
  field: (typeof FIELD_COPY)[number];
  snapshot: ModelPolicySnapshot;
  draft: ModelPolicyPatch;
  disabled: boolean;
  onChange: (patch: ModelPolicyPatch) => void;
}) {
  const current = (draft[field.key] ?? snapshot[field.key as keyof ModelPolicySnapshot]) as string | boolean;
  if (field.key === "defaultModelTier") {
    return (
      <label>
        {field.label}
        <select
          aria-label={field.label}
          value={String(current)}
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, defaultModelTier: event.target.value as ModelPolicyPatch["defaultModelTier"] })}
        >
          <option value="auto">Auto</option>
          <option value="flash">Flash</option>
          <option value="pro">Pro</option>
        </select>
      </label>
    );
  }
  if (typeof snapshot[field.key as keyof ModelPolicySnapshot] === "boolean") {
    return (
      <label>
        {field.label}
        <input
          type="checkbox"
          aria-label={field.label}
          checked={Boolean(current)}
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, [field.key]: event.target.checked })}
        />
      </label>
    );
  }
  return (
    <label>
      {field.label}
      <input
        aria-label={field.label}
        value={String(current)}
        disabled={disabled}
        onChange={(event) => onChange({ ...draft, [field.key]: event.target.value })}
      />
    </label>
  );
}

export function ModelPolicyPage() {
  const client = useQueryClient();
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities"),
  });
  const projectId = capabilities.data?.data?.projectId;
  const globalPolicy = useQuery({
    queryKey: ["model-policy", "global"],
    queryFn: () => api.get<ModelPolicySnapshot>("/api/v1/model-policy"),
    enabled: capabilities.isSuccess,
  });
  const projectPolicy = useQuery({
    queryKey: ["model-policy", "project", projectId],
    queryFn: () => api.get<ModelPolicySnapshot>(
      `/api/v1/model-policy?projectId=${encodeURIComponent(projectId ?? "")}`,
    ),
    enabled: capabilities.isSuccess && Boolean(projectId),
  });
  const balance = useQuery({
    queryKey: ["usage-balance"],
    queryFn: () => api.get<UsageBalanceSnapshot>("/api/v1/usage-balance"),
    enabled: capabilities.isSuccess,
  });
  const [scope, setScope] = useState<PolicyScope>("project");
  const [draft, setDraft] = useState<ModelPolicyPatch>({});
  const [confirm, setConfirm] = useState<ConfirmKind | null>(null);
  const [adoptedGlobal, setAdoptedGlobal] = useState<ModelPolicySnapshot | null>(null);
  const [adoptedProject, setAdoptedProject] = useState<ModelPolicySnapshot | null>(null);
  const [needsReconfirm, setNeedsReconfirm] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const cap = capabilities.data?.data;
  const activePolicy = scope === "global" ? globalPolicy : projectPolicy;
  const snapshot = scope === "global"
    ? adoptedGlobal ?? globalPolicy.data?.data ?? null
    : adoptedProject ?? projectPolicy.data?.data ?? null;
  const canMutate = capabilities.isSuccess
    && activePolicy.isSuccess
    && cap?.canSetModelPolicy === true
    && !envelopeHasErrors(capabilities.data)
    && !envelopeHasErrors(activePolicy.data)
    && !envelopeHasNonFreshSources(activePolicy.data);
  const mutation = useMutation({
    mutationFn: (request: { scope: PolicyScope; patch: ModelPolicyPatch | null; expectedRevision: number }) => {
      const encoded = encodeURIComponent(projectId ?? "");
      const path = request.scope === "global"
        ? "/api/v1/model-policy/global"
        : `/api/v1/model-policy/projects/${encoded}`;
      return api.command<CommandReceipt<ModelPolicySnapshot>>(
        path,
        { patch: request.patch, expectedRevision: request.expectedRevision },
      );
    },
  });

  async function save() {
    if (!canMutate || !snapshot || !confirm) return;
    try {
      const response = await mutation.mutateAsync({
        scope,
        patch: confirm === "inherit" ? null : draft,
        expectedRevision: snapshot.revision,
      });
      if (response.data?.snapshot) {
        const next = response.data.snapshot;
        if (scope === "global") {
          setAdoptedGlobal(next);
          client.setQueryData(["model-policy", "global"], { ...response, data: next });
        } else {
          setAdoptedProject(next);
          client.setQueryData(["model-policy", "project", projectId], { ...response, data: next });
        }
      }
      setDraft({});
      setConfirm(null);
      setNeedsReconfirm(false);
      setMutationError(null);
    } catch (error) {
      if (error instanceof ApiClientError && error.errors[0]?.code === "RESOURCE_CHANGED") {
        const resource = error.errors[0].details?.currentResource as ModelPolicySnapshot | undefined;
        if (resource) {
          if (scope === "global") setAdoptedGlobal(resource);
          else setAdoptedProject(resource);
        }
        setNeedsReconfirm(true);
        setConfirm(null);
        setMutationError(null);
      } else {
        setMutationError(error instanceof Error ? error.message : "模型策略写入失败");
        setConfirm(null);
      }
    }
  }

  function chooseScope(next: PolicyScope) {
    setScope(next);
    setDraft({});
    setConfirm(null);
    setNeedsReconfirm(false);
    setMutationError(null);
  }

  if (capabilities.isPending) {
    return <section className="page"><QueryLoading /></section>;
  }
  if (capabilities.isError || !cap) {
    return <section className="page"><QueryFailure title="控制台能力来源暂不可用" /></section>;
  }

  return (
    <section
      className="page model-policy-page"
      role={activePolicy.isPending ? undefined : "region"}
      aria-labelledby={activePolicy.isPending ? undefined : "model-policy-title"}
    >
      <header className="page-header page-header--split">
        <div>
          <p className="page-kicker">Control / 05</p>
          <h1 id="model-policy-title">模型策略</h1>
          <p className="lede">层级与预算跟科研自主模式分开。价格由服务端决定。</p>
        </div>
        <span className="profile-flag">{cap?.profile ?? "unknown"}</span>
      </header>
      <SourceStrip sources={capabilities.data?.sources ?? {}} />
      <EnvelopeErrors errors={capabilities.data?.errors ?? []} />
      <SourceStrip sources={activePolicy.data?.sources ?? {}} />
      <EnvelopeErrors errors={activePolicy.data?.errors ?? []} />
      <section className="section-block account-balance" aria-labelledby="balance-title">
        <div className="section-heading">
          <p>PROVIDER / BALANCE</p>
          <h2 id="balance-title">账户余额</h2>
        </div>
        {balance.isPending && <p className="muted">正在读取余额…</p>}
        {balance.isError && (
          <p className="command-notice" role="status">{balance.error.message || "余额来源暂不可用"}</p>
        )}
        {balance.data?.data && (
          <dl className="policy-meta balance-facts">
            <div><dt>可用余额</dt><dd>¥{balance.data.data.totalBalance}</dd></div>
            <div><dt>服务商</dt><dd>{balance.data.data.provider}</dd></div>
            <div><dt>观测时间</dt><dd>{new Date(balance.data.data.observedAt).toLocaleString("zh-CN")}</dd></div>
          </dl>
        )}
        {balance.data && <SourceStrip sources={balance.data.sources} />}
        {balance.data && <EnvelopeErrors errors={balance.data.errors} />}
      </section>
      <div className="policy-scope" role="group" aria-label="策略作用域">
        <button type="button" aria-pressed={scope === "project"} onClick={() => chooseScope("project")}>项目覆盖</button>
        <button type="button" aria-pressed={scope === "global"} onClick={() => chooseScope("global")}>全局默认</button>
      </div>
      {activePolicy.isPending ? (
        <section className="section-block"><QueryLoading /></section>
      ) : activePolicy.isError || !snapshot ? (
        <section className="section-block"><QueryFailure title="模型策略来源暂不可用" /></section>
      ) : <>
      <section className="section-block safety-baselines" aria-labelledby="safety-title">
        <div className="section-heading">
          <p>IMMUTABLE / SAFETY</p>
          <h2 id="safety-title">系统安全基线</h2>
        </div>
        <p className="muted"><strong>仅观察，不可关闭</strong>。它们不是项目开关，也不会被本页面覆盖。模型策略不属于科研自主模式。</p>
        <ul className="fact-list">
          {Object.entries(snapshot.hardSafetyBaselines).map(([key, enabled]) => (
            <li key={key}><span>{key}</span><strong>{enabled ? "已强制" : "需核查"}</strong></li>
          ))}
        </ul>
      </section>
      <section className="section-block policy-editor" aria-labelledby="policy-title">
        <div className="section-heading">
          <p>{scope === "global" ? "GLOBAL DEFAULTS" : "PROJECT DEFAULTS"}</p>
          <h2 id="policy-title">{scope === "global" ? "全局默认" : "项目默认"}</h2>
          <span>{scope === "global" ? "所有未覆盖项目的默认值" : snapshot.inheritsGlobal ? "继承全局" : "本项目覆盖全局默认"}</span>
        </div>
        <dl className="policy-meta">
          <div><dt>来源</dt><dd>{snapshot.source === "project" ? "项目覆盖" : "全局默认"}</dd></div>
          <div><dt>修订号</dt><dd>{snapshot.revision}</dd></div>
          <div>
            <dt>PriceCatalog</dt>
            <dd>{snapshot.priceCatalog.status} · {snapshot.priceCatalog.version ?? "—"}</dd>
          </div>
        </dl>
        <div className="policy-fields">
          {FIELD_COPY.map((field) => (
            <PolicyField
              key={field.key}
              field={field}
              snapshot={snapshot}
              draft={draft}
              disabled={!canMutate}
              onChange={setDraft}
            />
          ))}
        </div>
        <div className="policy-actions">
          <button
            type="button"
            className="secondary-action"
            disabled={!canMutate || scope === "global" || snapshot.inheritsGlobal}
            onClick={() => setConfirm("inherit")}
          >
            恢复继承全局
          </button>
          <button
            type="button"
            className="primary-action"
            disabled={!canMutate || Object.keys(draft).length === 0}
            onClick={() => setConfirm("save")}
          >
            {scope === "global" ? "保存全局默认" : "保存项目默认"}
          </button>
        </div>
        {!canMutate && !envelopeHasNonFreshSources(activePolicy.data) && (
          <p className="readonly-note">当前 profile 为 {cap?.profile ?? "unknown"}，只读，不能修改模型策略。</p>
        )}
        {envelopeHasNonFreshSources(activePolicy.data) && (
          <p className="command-notice" role="status">权威快照不是实时数据；刷新成功前禁止写入。</p>
        )}
        {needsReconfirm && (
          <p className="command-notice" role="status">审阅最新值后重新确认</p>
        )}
        {mutationError && <p className="command-error" role="alert">{mutationError}</p>}
      </section>
      <ConfirmDialog
        open={confirm !== null}
        title={confirm === "inherit" ? "确认恢复继承" : "确认保存模型策略"}
        confirmLabel={confirm === "inherit" ? "确认恢复继承" : "确认保存"}
        busy={mutation.isPending}
        onClose={() => setConfirm(null)}
        onConfirm={() => void save()}
      >
        <p>服务端将以当前修订号验证本次变更；冲突后不会自动重放。</p>
      </ConfirmDialog>
      </>}
    </section>
  );
}
