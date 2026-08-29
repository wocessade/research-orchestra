import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api, ApiClientError } from "../api/client";
import type {
  CapabilitySnapshot,
  CommandReceipt,
  DeploymentSummary,
  Envelope,
  RunSummary,
  Schemas,
} from "../api/types";
import { coerceDeploymentParameters } from "../pages/InfrastructurePage";
import { ModalDialog } from "./Dialogs";
import { EnvelopeErrors, SourceStrip, envelopeHasErrors } from "./EnvelopeState";

type RunPreparationPreview = Schemas["RunPreparationPreview"];
type RunPreparationPreviewRequest = Schemas["RunPreparationPreviewRequest"];
type AllowedRunPreferences = Schemas["AllowedRunPreferences"];
type PriceCatalog = Schemas["PriceCatalog"];
type Schema = {
  properties?: Record<string, { type?: string; title?: string; description?: string }>;
  required?: string[];
};

type Props = {
  deployment: DeploymentSummary | null;
  open: boolean;
  onClose: () => void;
  onSubmitted: (run: RunSummary) => void;
};

type PreparationForm = {
  intent: RunPreparationPreviewRequest["intent"];
  requestedModelTier: RunPreparationPreviewRequest["requestedModelTier"];
  deadline: string;
  workload: RunPreparationPreviewRequest["workload"];
  allowedPreferences: AllowedRunPreferences;
};

const defaultForm = (): PreparationForm => ({
  intent: "execute",
  requestedModelTier: "auto",
  deadline: "",
  workload: { expectedCalls: 1, inputTokens: 1000, outputTokens: 1000, runtimeMinutes: 5 },
  allowedPreferences: {
    allowAutoUpgrade: false,
    allowFlashDowngrade: true,
    autoResume: false,
    preferOffPeak: true,
  },
});

function CatalogFacts({ catalog }: { catalog: PriceCatalog }) {
  return (
    <dl className="dialog-facts catalog-facts">
      <div><dt>PriceCatalog</dt><dd>{catalog.status}</dd></div>
      <div><dt>版本</dt><dd>{catalog.version ?? "—"}</dd></div>
      <div><dt>生效</dt><dd>{catalog.effectiveAt ?? "—"}</dd></div>
      <div><dt>复核截止</dt><dd>{catalog.reviewBy ?? "—"}</dd></div>
      <div><dt>来源</dt><dd>{catalog.source ?? "—"}</dd></div>
    </dl>
  );
}

function PreviewFacts({ preview }: { preview: RunPreparationPreview }) {
  return (
    <section className="preview-ledger" aria-labelledby="preview-title">
      <h3 id="preview-title">服务端预览</h3>
      <dl className="dialog-facts">
        <div><dt>有效自主模式</dt><dd>{preview.effectiveAutonomyMode}</dd></div>
        <div><dt>实际层级</dt><dd>{preview.effectiveModelTier?.toUpperCase() ?? "—"}</dd></div>
        <div><dt>估算</dt><dd>{preview.budget.expectedCost} CNY</dd></div>
        <div><dt>上限</dt><dd>{preview.budget.authorizedCeiling} CNY</dd></div>
        <div><dt>价格期</dt><dd>{preview.pricePeriod} · {preview.scheduledStart ?? "立即"}</dd></div>
        <div><dt>Fallback</dt><dd>{preview.fallbackModelTier?.toUpperCase() ?? "—"}</dd></div>
      </dl>
      <p>预览来自服务端 PriceCatalog；修改输入后必须重新生成。</p>
    </section>
  );
}

function PreferenceFields({
  value,
  onChange,
}: {
  value: AllowedRunPreferences;
  onChange: (next: AllowedRunPreferences) => void;
}) {
  const fields: Array<[keyof AllowedRunPreferences, string]> = [
    ["preferOffPeak", "偏好低峰时段"],
    ["allowAutoUpgrade", "包内自动升级 Pro"],
    ["allowFlashDowngrade", "低风险允许 Flash 降级"],
    ["autoResume", "余额恢复后自动继续"],
  ];
  return (
    <>
      {fields.map(([key, label]) => (
        <label key={key}>
          <input
            type="checkbox"
            aria-label={label}
            checked={value[key]}
            onChange={(event) => onChange({ ...value, [key]: event.target.checked })}
          />
          {label}
        </label>
      ))}
    </>
  );
}

export function RunPreparation({ deployment, open, onClose, onSubmitted }: Props) {
  const [parameters, setParameters] = useState<Record<string, string>>({});
  const [advanced, setAdvanced] = useState(false);
  const [form, setForm] = useState<PreparationForm>(defaultForm);
  const [previewEnvelope, setPreviewEnvelope] = useState<Envelope<RunPreparationPreview> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitErrors, setSubmitErrors] = useState<Envelope<unknown>["errors"]>([]);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const schema = deployment?.parameterSchema as Schema | undefined;
  const fields = Object.entries(schema?.properties ?? {});
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities"),
    enabled: open,
  });
  const policy = useQuery({
    queryKey: ["model-policy"],
    queryFn: () => api.get<Schemas["ModelPolicySnapshot"]>("/api/v1/model-policy"),
    enabled: open,
  });
  const cap = capabilities.data?.data;
  const catalog = policy.data?.data?.priceCatalog;
  const canPrepare = capabilities.isSuccess
    && policy.isSuccess
    && cap?.canPreparePaidRun === true
    && cap?.canSubmitRegisteredDeployment === true
    && !envelopeHasErrors(capabilities.data)
    && !envelopeHasErrors(policy.data)
    && catalog?.status === "ready";
  const preview = previewEnvelope?.data ?? null;
  const previewBlocked = envelopeHasErrors(previewEnvelope ?? undefined);

  useEffect(() => {
    if (open && deployment) {
      setParameters({});
      setAdvanced(false);
      setForm(defaultForm());
      setPreviewEnvelope(null);
      setError(null);
      setSubmitErrors([]);
      setIdempotencyKey(`bogda-console-${deployment.deploymentId}-${Date.now()}`);
    }
  }, [open, deployment]);

  const request = useMemo<RunPreparationPreviewRequest>(() => ({
    projectId: cap?.projectId ?? "bogda-main",
    intent: form.intent,
    requestedModelTier: form.requestedModelTier,
    workload: form.workload,
    allowedPreferences: form.allowedPreferences,
    deadline: form.deadline || null,
  }), [cap?.projectId, form]);

  const previewMutation = useMutation({
    mutationFn: () => api.command<RunPreparationPreview>("/api/v1/run-preparations/preview", request),
  });
  const submitMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => (
      api.command<CommandReceipt<RunSummary>>(`/api/v1/deployments/${deployment!.deploymentId}/runs`, body)
    ),
  });
  const submitting = submitMutation.isPending;

  function invalidatePreview() {
    setPreviewEnvelope(null);
    setError(null);
    setSubmitErrors([]);
  }

  function updateForm(next: PreparationForm) {
    setForm(next);
    invalidatePreview();
  }

  async function makePreview() {
    if (!deployment || !canPrepare) return;
    try {
      const response = await previewMutation.mutateAsync();
      setPreviewEnvelope({
        data: response.data,
        sources: response.sources ?? {},
        errors: response.errors ?? [],
      });
      setError(response.data ? null : "预览不可用");
    } catch (caught) {
      if (caught instanceof ApiClientError) {
        setPreviewEnvelope({
          data: null,
          sources: caught.envelope.sources ?? {},
          errors: caught.envelope.errors,
        });
        setError(caught.message);
        return;
      }
      setError(caught instanceof Error ? caught.message : "预览不可用");
    }
  }

  async function submit() {
    if (!preview || !deployment || previewBlocked || !canPrepare || submitting) return;
    try {
      const typed = coerceDeploymentParameters(parameters, schema);
      const response = await submitMutation.mutateAsync({
        parameters: typed,
        idempotencyKey,
        runPreparationId: preview.preparationId,
      });
      if (response.data?.snapshot) {
        onSubmitted(response.data.snapshot);
        onClose();
      } else {
        setSubmitErrors(response.errors ?? []);
        setError("提交未获得权威回执；没有自动重试。");
      }
    } catch (caught) {
      if (caught instanceof ApiClientError) {
        setSubmitErrors(caught.envelope.errors);
        setError("提交未获得权威回执；没有自动重试。");
        return;
      }
      if (caught instanceof Error) {
        setError(caught.message);
        return;
      }
      setError("提交未获得权威回执；没有自动重试。");
    }
  }

  function requestClose() {
    if (submitting) return;
    onClose();
  }

  return (
    <ModalDialog
      open={open}
      title={`准备 ${deployment?.name ?? "Deployment"}`}
      onClose={requestClose}
      busy={submitting}
      footer={(
        <>
          <button type="button" className="secondary-action" data-autofocus onClick={requestClose} disabled={submitting}>
            返回
          </button>
          {preview ? (
            <>
              <button type="button" className="quiet-action" onClick={() => { if (!submitting) invalidatePreview(); }} disabled={submitting}>
                修改准备信息
              </button>
              <button
                type="button"
                className="primary-action"
                onClick={() => void submit()}
                disabled={!canPrepare || submitting || previewBlocked}
              >
                确认并提交运行
              </button>
            </>
          ) : (
            <button
              type="button"
              className="primary-action"
              onClick={() => void makePreview()}
              disabled={!canPrepare || previewMutation.isPending}
            >
              生成服务端预览
            </button>
          )}
        </>
      )}
    >
      <SourceStrip sources={capabilities.data?.sources ?? {}} />
      <EnvelopeErrors errors={capabilities.data?.errors ?? []} />
      <SourceStrip sources={policy.data?.sources ?? {}} />
      <EnvelopeErrors errors={policy.data?.errors ?? []} />
      {catalog && <CatalogFacts catalog={catalog} />}
      {!canPrepare && (
        <p className="readonly-note">当前 profile 未显式开放准备/提交能力，不能执行付费运行。</p>
      )}
      <div className="parameter-fields">
        {fields.map(([name, property]) => (
          <label key={name}>
            {property.title ?? name}
            <input
              aria-label={property.title ?? name}
              value={parameters[name] ?? ""}
              required={schema?.required?.includes(name)}
              onChange={(event) => {
                setParameters((current) => ({ ...current, [name]: event.target.value }));
                invalidatePreview();
              }}
            />
            <small>{property.description ?? name}</small>
          </label>
        ))}
      </div>
      {!preview && (
        <>
          <p className="seed-note">下面是预览请求，不是报价。费用和档位以生成后的服务端预览为准。</p>
          <label>
            研究意图
            <select
              aria-label="研究意图"
              value={form.intent}
              onChange={(event) => updateForm({ ...form, intent: event.target.value as PreparationForm["intent"] })}
            >
              <option value="execute">执行</option>
              <option value="brief">简报</option>
              <option value="explore">探索</option>
              <option value="decide">决策</option>
              <option value="audit">审计</option>
            </select>
          </label>
          <label>
            模型层级
            <select
              aria-label="模型层级"
              value={form.requestedModelTier}
              onChange={(event) => updateForm({
                ...form,
                requestedModelTier: event.target.value as PreparationForm["requestedModelTier"],
              })}
            >
              <option value="auto">Auto</option>
              <option value="flash">Flash</option>
              <option value="pro">Pro</option>
            </select>
          </label>
          <button type="button" className="quiet-action" onClick={() => setAdvanced((value) => !value)}>
            {advanced ? "收起工作量与截止时间" : "展开工作量与截止时间"}
          </button>
          {advanced && (
            <div className="parameter-fields prep-advanced">
              <label>
                输入 tokens
                <input
                  aria-label="输入 tokens"
                  type="number"
                  value={form.workload.inputTokens}
                  onChange={(event) => updateForm({
                    ...form,
                    workload: { ...form.workload, inputTokens: Number(event.target.value) },
                  })}
                />
              </label>
              <label>
                输出 tokens
                <input
                  aria-label="输出 tokens"
                  type="number"
                  value={form.workload.outputTokens}
                  onChange={(event) => updateForm({
                    ...form,
                    workload: { ...form.workload, outputTokens: Number(event.target.value) },
                  })}
                />
              </label>
              <label>
                预计调用次数
                <input
                  aria-label="预计调用次数"
                  type="number"
                  value={form.workload.expectedCalls}
                  onChange={(event) => updateForm({
                    ...form,
                    workload: { ...form.workload, expectedCalls: Number(event.target.value) },
                  })}
                />
              </label>
              <label>
                运行分钟
                <input
                  aria-label="运行分钟"
                  type="number"
                  value={form.workload.runtimeMinutes}
                  onChange={(event) => updateForm({
                    ...form,
                    workload: { ...form.workload, runtimeMinutes: Number(event.target.value) },
                  })}
                />
              </label>
              <label>
                截止时间
                <input
                  aria-label="截止时间"
                  type="text"
                  value={form.deadline}
                  onChange={(event) => updateForm({ ...form, deadline: event.target.value })}
                />
              </label>
              <PreferenceFields
                value={form.allowedPreferences}
                onChange={(allowedPreferences) => updateForm({ ...form, allowedPreferences })}
              />
            </div>
          )}
        </>
      )}
      {preview && <PreviewFacts preview={preview} />}
      <SourceStrip sources={previewEnvelope?.sources ?? {}} />
      <EnvelopeErrors errors={previewEnvelope?.errors ?? []} />
      <EnvelopeErrors errors={submitErrors} />
      {error && <p className="command-error" role="alert">{error}</p>}
    </ModalDialog>
  );
}
