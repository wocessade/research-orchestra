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

type ScalarPolicyKey = "minimumRemaining" | "workloadSafetyMargin";
type SwitchPolicyKey = "allowAutoUpgrade" | "allowFlashDowngrade" | "preferOffPeak" | "autoResume" | "criticalNotifications";

function formatProviderName(provider: string) {
  if (provider.toLowerCase() === "deepseek") return "DeepSeek";
  return provider;
}

const SCALAR_FIELDS: Array<{ key: ScalarPolicyKey; label: string; description: string; suffix: string }> = [
  {
    key: "minimumRemaining",
    label: "最低剩余预算",
    description: "每次准入后必须留在账户中的最低余额。",
    suffix: "CNY",
  },
  {
    key: "workloadSafetyMargin",
    label: "工作量安全余量",
    description: "放大预计工作量，为科研过程中的不确定性留出预算。",
    suffix: "×",
  },
];

const ROUTING_SWITCHES: Array<{ key: SwitchPolicyKey; label: string; description: string }> = [
  { key: "allowAutoUpgrade", label: "包内自动升级 Pro", description: "Auto 在预算允许时可升级到 Pro。" },
  { key: "allowFlashDowngrade", label: "低风险允许 Flash 降级", description: "低风险工作可回落到 Flash，降低费用和等待。" },
];

const OPERATIONS_SWITCHES: Array<{ key: SwitchPolicyKey; label: string; description: string }> = [
  { key: "preferOffPeak", label: "偏好低峰时段", description: "在 deadline 允许时优先安排低峰价格窗口。" },
  { key: "autoResume", label: "余额恢复后自动继续", description: "余额恢复并通过预算重检后继续运行。" },
  { key: "criticalNotifications", label: "关键通知", description: "需要裁决、预算风险或恢复事件时通知你。" },
];

const MODEL_TIERS = [
  { value: "auto", label: "Auto", description: "按任务风险和预算自动选择" },
  { value: "flash", label: "Flash", description: "优先速度与成本" },
  { value: "pro", label: "Pro", description: "优先复杂科研能力" },
] as const;

function envelopeHasErrors(envelope: Envelope<unknown> | undefined) {
  return Boolean(envelope?.errors.length);
}

function ScalarPolicyField({
  field,
  snapshot,
  draft,
  disabled,
  onChange,
}: {
  field: (typeof SCALAR_FIELDS)[number];
  snapshot: ModelPolicySnapshot;
  draft: ModelPolicyPatch;
  disabled: boolean;
  onChange: (patch: ModelPolicyPatch) => void;
}) {
  const current = draft[field.key] ?? snapshot[field.key];
  return (
    <label className="policy-scalar-field">
      <span className="policy-field-copy">
        <strong>{field.label}</strong>
        <small>{field.description}</small>
      </span>
      <span className="policy-input-shell">
        <input
          aria-label={field.label}
          value={String(current)}
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, [field.key]: event.target.value })}
        />
        <span aria-hidden="true">{field.suffix}</span>
      </span>
    </label>
  );
}

function PolicySwitch({
  field,
  snapshot,
  draft,
  disabled,
  onChange,
}: {
  field: (typeof ROUTING_SWITCHES)[number] | (typeof OPERATIONS_SWITCHES)[number];
  snapshot: ModelPolicySnapshot;
  draft: ModelPolicyPatch;
  disabled: boolean;
  onChange: (patch: ModelPolicyPatch) => void;
}) {
  const current = draft[field.key] ?? snapshot[field.key];
  return (
    <label className="policy-switch-row">
      <span className="policy-field-copy">
        <strong>{field.label}</strong>
        <small>{field.description}</small>
      </span>
      <input
        type="checkbox"
        role="switch"
        aria-label={field.label}
        checked={Boolean(current)}
        disabled={disabled}
        onChange={(event) => onChange({ ...draft, [field.key]: event.target.checked })}
      />
      <span className="policy-switch-track" aria-hidden="true" />
    </label>
  );
}

function ModelTierField({
  snapshot,
  draft,
  disabled,
  onChange,
}: {
  snapshot: ModelPolicySnapshot;
  draft: ModelPolicyPatch;
  disabled: boolean;
  onChange: (patch: ModelPolicyPatch) => void;
}) {
  const current = draft.defaultModelTier ?? snapshot.defaultModelTier;
  return (
    <fieldset className="model-tier-field" aria-label="默认模型层级">
      <legend>默认模型层级</legend>
      <div className="model-tier-options">
        {MODEL_TIERS.map((tier) => (
          <label key={tier.value}>
            <input
              type="radio"
              name="default-model-tier"
              value={tier.value}
              checked={current === tier.value}
              disabled={disabled}
              onChange={() => onChange({ ...draft, defaultModelTier: tier.value })}
            />
            <span>
              <strong>{tier.label}</strong>
              <small>{tier.description}</small>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
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
  const [editingInherited, setEditingInherited] = useState(false);
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
      setEditingInherited(false);
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
    setEditingInherited(false);
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
        {balance.isPending && (
          <>
            <h2 id="balance-title">账户余额</h2>
            <p className="muted">正在读取余额…</p>
          </>
        )}
        {balance.isError && (
          <>
            <h2 id="balance-title">账户余额</h2>
            <p className="command-notice" role="status">{balance.error.message || "余额来源暂不可用"}</p>
          </>
        )}
        {balance.data?.data && (
          <>
            <p className="account-balance__provider">{formatProviderName(balance.data.data.provider)}</p>
            <h2 id="balance-title">账户余额</h2>
            <p className="account-balance__amount">¥{balance.data.data.totalBalance}</p>
            <p className="account-balance__meta">
              官方账户 · 只读观测 · {new Date(balance.data.data.observedAt).toLocaleString("zh-CN")}
            </p>
          </>
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
          <span>{scope === "global" ? "所有未覆盖项目的默认值" : editingInherited ? "正在创建覆盖" : snapshot.inheritsGlobal ? "继承全局" : "本项目覆盖全局默认"}</span>
        </div>
        <div className="policy-lineage" aria-label="策略继承关系">
          <span className="policy-lineage__text">
            {scope === "global"
              ? "全局策略 → 默认基准"
              : snapshot.inheritsGlobal
                ? "全局策略 → 项目默认"
                : "全局策略 → 项目覆盖"}
          </span>
          <span className={`policy-lineage__state ${editingInherited ? "is-draft" : snapshot.inheritsGlobal ? "is-inherited" : "is-local"}`}>
            {scope === "global" ? "全局基准" : editingInherited ? "准备覆盖" : snapshot.inheritsGlobal ? "继承中" : "本项目生效"}
          </span>
        </div>
        <dl className="policy-meta policy-meta--compact">
          <div><dt>来源</dt><dd>{snapshot.source === "project" ? "项目覆盖" : "全局默认"}</dd></div>
          <div><dt>修订号</dt><dd>{snapshot.revision}</dd></div>
          <div>
            <dt>价格目录</dt>
            <dd>{snapshot.priceCatalog.status} · {snapshot.priceCatalog.version ?? "—"}</dd>
          </div>
        </dl>
        {scope === "project" && snapshot.inheritsGlobal && !editingInherited ? (
          <div className="policy-effective-summary">
            <div className="policy-effective-summary__intro">
              <p>EFFECTIVE POLICY</p>
              <h3>当前生效策略</h3>
              <span>这个项目没有单独覆盖，以下值由全局策略提供。</span>
            </div>
            <dl className="policy-effective-values" aria-label="当前生效策略明细">
              <div><dt>最低剩余</dt><dd>¥{snapshot.minimumRemaining}</dd></div>
              <div><dt>安全余量</dt><dd>{snapshot.workloadSafetyMargin}×</dd></div>
              <div><dt>模型层级</dt><dd>{snapshot.defaultModelTier.toUpperCase()}</dd></div>
              <div><dt>价格窗口</dt><dd>{snapshot.preferOffPeak ? "低峰优先" : "即时可用"}</dd></div>
              <div><dt>自动升级 Pro</dt><dd>{snapshot.allowAutoUpgrade ? "允许" : "关闭"}</dd></div>
              <div><dt>Flash 降级</dt><dd>{snapshot.allowFlashDowngrade ? "允许" : "关闭"}</dd></div>
              <div><dt>余额恢复</dt><dd>{snapshot.autoResume ? "自动继续" : "手动继续"}</dd></div>
              <div><dt>关键通知</dt><dd>{snapshot.criticalNotifications ? "开启" : "关闭"}</dd></div>
            </dl>
            <button
              type="button"
              className="primary-action policy-create-override"
              disabled={!canMutate}
              onClick={() => setEditingInherited(true)}
            >
              创建项目覆盖
            </button>
          </div>
        ) : (
          <div className="policy-form">
            <fieldset className="policy-form-section" aria-labelledby="budget-policy-title">
              <div className="policy-form-section__intro">
                <p>01 / BUDGET</p>
                <h3 id="budget-policy-title">预算与安全余量</h3>
                <span>定义每次模型准入必须守住的财务边界。</span>
              </div>
              <div className="policy-form-section__controls policy-scalar-grid">
                {SCALAR_FIELDS.map((field) => (
                  <ScalarPolicyField
                    key={field.key}
                    field={field}
                    snapshot={snapshot}
                    draft={draft}
                    disabled={!canMutate}
                    onChange={setDraft}
                  />
                ))}
              </div>
            </fieldset>
            <fieldset className="policy-form-section" aria-labelledby="routing-policy-title">
              <div className="policy-form-section__intro">
                <p>02 / ROUTING</p>
                <h3 id="routing-policy-title">模型路由</h3>
                <span>先选默认层级，再规定 Auto 可以怎样调整。</span>
              </div>
              <div className="policy-form-section__controls">
                <ModelTierField snapshot={snapshot} draft={draft} disabled={!canMutate} onChange={setDraft} />
                <div className="policy-switch-list">
                  {ROUTING_SWITCHES.map((field) => (
                    <PolicySwitch
                      key={field.key}
                      field={field}
                      snapshot={snapshot}
                      draft={draft}
                      disabled={!canMutate}
                      onChange={setDraft}
                    />
                  ))}
                </div>
              </div>
            </fieldset>
            <fieldset className="policy-form-section" aria-labelledby="operations-policy-title">
              <div className="policy-form-section__intro">
                <p>03 / OPERATIONS</p>
                <h3 id="operations-policy-title">调度与恢复</h3>
                <span>控制价格窗口、余额恢复和需要你关注的通知。</span>
              </div>
              <div className="policy-form-section__controls policy-switch-list">
                {OPERATIONS_SWITCHES.map((field) => (
                  <PolicySwitch
                    key={field.key}
                    field={field}
                    snapshot={snapshot}
                    draft={draft}
                    disabled={!canMutate}
                    onChange={setDraft}
                  />
                ))}
              </div>
            </fieldset>
            <div className="policy-actions">
              {scope === "project" && snapshot.inheritsGlobal && editingInherited && (
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => {
                    setDraft({});
                    setConfirm(null);
                    setNeedsReconfirm(false);
                    setMutationError(null);
                    setEditingInherited(false);
                  }}
                >
                  取消创建覆盖
                </button>
              )}
              {scope === "project" && !snapshot.inheritsGlobal && (
                <button
                  type="button"
                  className="secondary-action"
                  disabled={!canMutate}
                  onClick={() => setConfirm("inherit")}
                >
                  恢复继承全局
                </button>
              )}
              <button
                type="button"
                className="primary-action"
                disabled={!canMutate || Object.keys(draft).length === 0}
                onClick={() => setConfirm("save")}
              >
                {scope === "global" ? "保存全局默认" : "保存项目默认"}
              </button>
            </div>
          </div>
        )}
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
