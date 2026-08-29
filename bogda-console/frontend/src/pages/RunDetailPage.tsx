import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";

import { api, ApiClientError } from "../api/client";
import type { CapabilitySnapshot, CommandReceipt, Page, RunDetail, RunResultVersion, RunResultView, RunSummary } from "../api/types";
import { ConfirmDialog } from "../components/Dialogs";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip, envelopeHasErrors } from "../components/EnvelopeState";
import { RunBudgetPanel } from "../components/RunBudgetPanel";
import { ExecutionMark, ScientificMark } from "../components/StatusMark";
import { SCIENTIFIC_REVIEW_ID } from "../scientificReview";

function formatAbsolute(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function ResultPanel({ view, executionType }: { view: RunResultView; executionType: string }) {
  if (view.availability === "missing") return <div className="result-alert result-alert--missing"><p className="page-kicker">RESULT / MISSING</p><h2>RunResult 缺失</h2><p>该运行尚无同 key、同 type 的 RunResult Artifact；科研状态不可用。</p></div>;
  if (view.availability === "invalid" || !view.result) return <div className="result-alert result-alert--invalid"><p className="page-kicker">RESULT / INVALID</p><h2>最新 RunResult 无效</h2><p className="mono">{view.artifactId}</p><ul>{view.validationIssues?.map((issue) => <li key={issue}>{issue}</li>)}</ul><p>较早版本不会覆盖最新版本的权威性。</p></div>;

  const result = view.result;
  const declaredComplete = result.declared_artifacts.length > 0 && result.declared_artifacts.every((artifact) => artifact.exists);
  return <>
    <div className="result-summary"><p className="page-kicker">RESULT / LATEST</p><h2>{result.summary}</h2><p>{executionType === "COMPLETED" && declaredComplete ? "执行完成，且声明的必要产物存在；这不代表科研结论已被接受。" : "RunResult 记录科研证据；Prefect 执行状态仍独立展示。"}</p><dl className="fact-grid"><div><dt>Artifact</dt><dd>{view.artifactId}</dd></div><div><dt>Executor</dt><dd>{result.executor}</dd></div><div><dt>Attempt</dt><dd>{result.attempt}</dd></div><div><dt>完成时间</dt><dd>{formatAbsolute(result.finished_at)}</dd></div></dl></div>
    <section className="detail-section" aria-labelledby="artifacts-title"><div className="detail-heading"><h2 id="artifacts-title">声明产物</h2><p>仅显示 RunResult 声明的产物，不扫描其他目录。</p></div>{result.declared_artifacts.length ? <ul className="artifact-list">{result.declared_artifacts.map((artifact) => <li key={artifact.uri}><span aria-hidden="true">{artifact.exists ? "◆" : "◇"}</span><div><strong>{artifact.uri}</strong><small>{artifact.kind} · {artifact.exists ? "已声明存在" : "声明缺失"} · {artifact.sizeBytes ?? "—"} bytes</small></div></li>)}</ul> : <p className="muted">RunResult 未声明产物。</p>}</section>
  </>;
}

function ReviewControl({ runId, view, enabled, profile, onReviewed }: { runId: string; view: RunResultView; enabled: boolean; profile?: string; onReviewed: (view: RunResultView) => void }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("accepted");
  const [summary, setSummary] = useState("");
  const [baseArtifactId, setBaseArtifactId] = useState(view.artifactId ?? "");
  const [adoptedArtifactId, setAdoptedArtifactId] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: () => api.command<CommandReceipt<RunResultView>>(`/api/v1/runs/${runId}/reviews`, { baseArtifactId, scientificStatus: status, reviewSummary: summary || null }) });
  const conflict = mutation.error instanceof ApiClientError && mutation.error.errors[0]?.code === "REVIEW_CONFLICT"
    ? mutation.error.errors[0].details?.currentResource as RunResultView | undefined
    : undefined;

  useEffect(() => {
    setBaseArtifactId(view.artifactId ?? "");
    setAdoptedArtifactId(null);
  }, [view.artifactId]);

  async function submit() {
    const response = await mutation.mutateAsync().catch(() => null);
    if (!response?.data) return;
    onReviewed(response.data.snapshot);
    await queryClient.invalidateQueries({ queryKey: ["result-versions", runId] });
    await queryClient.invalidateQueries({ queryKey: ["reviews"] });
  }

  return <section id={SCIENTIFIC_REVIEW_ID} className="review-control detail-section" aria-labelledby="review-form-title">
    <div className="detail-heading"><div><p className="page-kicker">Append only</p><h2 id="review-form-title">追加科研评审</h2></div><p>提交会创建新的 RunResult Artifact 版本，不改写 Prefect 执行历史。</p></div>
    <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <label>科研判断<select value={status} onChange={(event) => setStatus(event.target.value)} disabled={!enabled || mutation.isPending}><option value="accepted">accepted / 接受</option><option value="rejected">rejected / 拒绝</option><option value="inconclusive">inconclusive / 无定论</option></select></label>
      <label>评审说明<textarea rows={4} value={summary} onChange={(event) => setSummary(event.target.value)} disabled={!enabled || mutation.isPending} /></label>
      <button type="submit" className="primary-action" disabled={!enabled || mutation.isPending}>{mutation.isPending ? "等待 RunResult 回执…" : "提交评审"}</button>
    </form>
    {!enabled && <p className="readonly-note">当前 profile 为 {profile ?? "unknown"}，只读，不能提交科研评审。</p>}
    {conflict && <div className="command-conflict" role="alert"><strong>结果已被其他评审更新</strong><span>表单内容已保留。请先检查最新 Artifact：</span><code>{conflict.artifactId}</code><button type="button" className="quiet-action" onClick={() => { if (!conflict.artifactId) return; setBaseArtifactId(conflict.artifactId); setAdoptedArtifactId(conflict.artifactId); mutation.reset(); }}>确认采用最新版本</button></div>}
    {adoptedArtifactId && <p className="command-notice" role="status">已确认采用最新 Artifact {adoptedArtifactId}；再次提交将创建新版本。</p>}
    {mutation.isError && !conflict && <div className="command-error" role="alert">评审未获得权威回执；没有自动重试。</div>}
  </section>;
}

function CheckpointControl({
  runId,
  checkpoint,
  enabled,
  profile,
  onDecided,
}: {
  runId: string;
  checkpoint: NonNullable<RunDetail["checkpoint"]>;
  enabled: boolean;
  profile?: string;
  onDecided: (detail: RunDetail) => void;
}) {
  const [rationale, setRationale] = useState("");
  const [commandVersion, setCommandVersion] = useState(checkpoint.commandVersion);
  const [adoptedVersion, setAdoptedVersion] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: (verdict: "approved" | "rejected") => api.command<CommandReceipt<RunDetail>>(`/api/v1/runs/${runId}/checkpoints`, {
      expectedCommandVersion: commandVersion,
      verdict,
      rationale: rationale || null,
    }),
  });
  const conflict = mutation.error instanceof ApiClientError && mutation.error.errors[0]?.code === "RESOURCE_CHANGED"
    ? mutation.error.errors[0].details?.currentResource as NonNullable<RunDetail["checkpoint"]> | undefined
    : undefined;

  useEffect(() => {
    setCommandVersion(checkpoint.commandVersion);
    setAdoptedVersion(null);
  }, [checkpoint.commandVersion]);

  async function decide(verdict: "approved" | "rejected") {
    const response = await mutation.mutateAsync(verdict).catch(() => null);
    if (!response?.data) return;
    onDecided(response.data.snapshot);
  }

  if (checkpoint.verdict) return null;

  return <section className="checkpoint-control detail-section" aria-labelledby="checkpoint-title">
    <div className="detail-heading">
      <div>
        <p className="page-kicker">Type-B / {checkpoint.stage}</p>
        <h2 id="checkpoint-title">人工检查点</h2>
      </div>
      <p>证据在本页；批准或拒绝只作用这一次检查点，不会从列表一键代劳。</p>
    </div>
    <dl className="fact-grid">
      <div><dt>类型</dt><dd>{checkpoint.kind}</dd></div>
      <div><dt>阶段</dt><dd>{checkpoint.stage}</dd></div>
      <div><dt>影响</dt><dd>{checkpoint.impact}</dd></div>
    </dl>
    <label>判断说明<textarea rows={3} value={rationale} onChange={(event) => setRationale(event.target.value)} disabled={!enabled || mutation.isPending} /></label>
    <div className="checkpoint-actions">
      <button type="button" className="primary-action" disabled={!enabled || mutation.isPending} onClick={() => void decide("approved")}>{mutation.isPending ? "等待回执…" : "批准"}</button>
      <button type="button" className="danger-outline-action" disabled={!enabled || mutation.isPending} onClick={() => void decide("rejected")}>拒绝</button>
    </div>
    {!enabled && <p className="readonly-note">当前 profile 为 {profile ?? "unknown"}，只读，不能决定人工检查点。</p>}
    {conflict && <div className="command-conflict" role="alert"><strong>检查点已被更新</strong><span>说明已保留。请先采用当前版本后再提交。</span><code>{conflict.commandVersion}</code><button type="button" className="quiet-action" onClick={() => { if (!conflict.commandVersion) return; setCommandVersion(conflict.commandVersion); setAdoptedVersion(conflict.commandVersion); mutation.reset(); }}>采用当前版本</button></div>}
    {adoptedVersion && <p className="command-notice" role="status">已采用当前检查点版本 {adoptedVersion}。</p>}
    {mutation.isError && !conflict && <div className="command-error" role="alert">检查点未获得权威回执；没有自动重试。</div>}
  </section>;
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const location = useLocation();
  const detailQuery = useQuery({ queryKey: ["run", runId], queryFn: () => api.get<RunDetail>(`/api/v1/runs/${runId}`) });
  const resultQuery = useQuery({ queryKey: ["result", runId], queryFn: () => api.get<RunResultView>(`/api/v1/runs/${runId}/result`) });
  const versionsQuery = useQuery({ queryKey: ["result-versions", runId], queryFn: () => api.get<Page<RunResultVersion>>(`/api/v1/runs/${runId}/result/versions`) });
  const capabilitiesQuery = useQuery({ queryKey: ["capabilities"], queryFn: () => api.get<CapabilitySnapshot>("/api/v1/capabilities") });
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelSnapshot, setCancelSnapshot] = useState<RunSummary | null>(null);
  const [reviewSnapshot, setReviewSnapshot] = useState<RunResultView | null>(null);
  const [detailSnapshot, setDetailSnapshot] = useState<RunDetail | null>(null);
  const cancelMutation = useMutation({ mutationFn: (run: RunSummary) => api.command<CommandReceipt<RunSummary>>(`/api/v1/runs/${run.runId}/cancel`, { expectedCommandVersion: run.commandVersion }) });
  const resultView = reviewSnapshot ?? resultQuery.data?.data;

  useEffect(() => {
    if (location.hash !== `#${SCIENTIFIC_REVIEW_ID}`) return;
    document.getElementById(SCIENTIFIC_REVIEW_ID)?.scrollIntoView();
  }, [location.hash, resultView?.availability]);

  if (detailQuery.isPending) return <section className="page"><QueryLoading /></section>;
  if (detailQuery.isError || !detailQuery.data.data) return <section className="page"><QueryFailure title="运行详情暂不可用" /></section>;
  const envelope = detailQuery.data;
  const detail = detailSnapshot ?? envelope.data!;
  const run = cancelSnapshot ?? detail.run;
  const science = reviewSnapshot?.result ? { availability: "available", artifactId: reviewSnapshot.artifactId, artifactCreatedAt: reviewSnapshot.artifactCreatedAt, scientificStatus: reviewSnapshot.result.scientific_status, reviewSummary: reviewSnapshot.result.review_summary, validationIssues: [] } : run.scientific;
  const capabilities = capabilitiesQuery.data?.data;
  const capReady = capabilitiesQuery.isSuccess && !envelopeHasErrors(capabilitiesQuery.data);
  const canCancel = capReady && capabilities?.canCancelRun === true;
  const canReview = capReady && capabilities?.canReviewScientificResult === true;

  async function cancelRun() {
    const response = await cancelMutation.mutateAsync(run).catch(() => null);
    if (!response?.data) return;
    setCancelSnapshot(response.data.snapshot);
    setCancelOpen(false);
  }

  return <article className="page run-detail">
    <Link className="back-link" to="/runs">← 返回运行账簿</Link>
    <header className="page-header page-header--split"><div><p className="page-kicker">Run / {run.runId}</p><h1>{run.name}</h1><p className="lede">{run.deploymentName ?? "未注册 Deployment"} · {run.workPoolName ?? "—"} / {run.workQueueName ?? "—"}</p></div>{!run.state.terminal && <button type="button" className="danger-outline-action" disabled={!canCancel} onClick={() => setCancelOpen(true)}>取消运行</button>}</header>
    <SourceStrip sources={{ ...envelope.sources, ...(resultQuery.data?.sources ?? {}) }} />
    <EnvelopeErrors errors={[...envelope.errors, ...(resultQuery.data?.errors ?? [])]} />
    <section className="authority-bands" aria-label="执行与科研状态">
      <div><p>Prefect 执行状态</p><ExecutionMark type={run.state.type} name={run.state.name} /><time dateTime={run.state.timestamp}>{formatAbsolute(run.state.timestamp)}</time></div>
      <div><p>科研判断状态</p>{science?.availability === "available" ? <ScientificMark status={science.scientificStatus} /> : <span className={`availability availability--${science?.availability ?? "none"}`}>{science?.availability === "invalid" ? "RunResult 无效" : science?.availability === "missing" ? "RunResult 缺失" : "科研状态不可用"}</span>}<span>{science?.artifactId ?? "无权威 Artifact"}</span></div>
    </section>
    <section className="detail-section context-section" aria-labelledby="context-title"><div className="detail-heading"><h2 id="context-title">项目上下文</h2><p>只读上下文。有效自主模式在创建时冻结，不在此修改。</p></div>{detail.projectContext ? <dl className="fact-grid"><div><dt>项目</dt><dd>{detail.projectContext.projectId}</dd></div><div><dt>冻结模式</dt><dd>{detail.projectContext.effectiveAutonomyMode}</dd></div><div><dt>模式来源</dt><dd>{detail.projectContext.modeSource}</dd></div><div><dt>可写</dt><dd>否</dd></div></dl> : <p className="muted">项目上下文不可用。</p>}</section>
    <RunBudgetPanel runId={runId} />
    {detail.checkpoint && !detail.checkpoint.verdict && <CheckpointControl runId={runId} checkpoint={detail.checkpoint} enabled={canReview} profile={capabilities?.profile} onDecided={setDetailSnapshot} />}
    {resultQuery.isPending && <QueryLoading />}
    {resultQuery.isError && <QueryFailure title="RunResult 暂不可用" />}
    {resultView && <ResultPanel view={resultView} executionType={run.state.type} />}
    {resultView?.availability === "available" && resultView.result && <ReviewControl runId={runId} view={resultView} enabled={canReview} profile={capabilities?.profile} onReviewed={setReviewSnapshot} />}
    <section className="detail-section" aria-labelledby="versions-title"><div className="detail-heading"><h2 id="versions-title">RunResult 版本</h2><p>由新到旧；第一条是当前科研权威版本。</p></div>{versionsQuery.data?.data?.items.length ? <ol className="version-list">{versionsQuery.data.data.items.map((version, index) => <li key={version.artifactId}><span>{index === 0 ? "当前" : `历史 ${index}`}</span><strong>{version.artifactId}</strong><time dateTime={version.createdAt}>{formatAbsolute(version.createdAt)}</time><em>{version.availability}</em></li>)}</ol> : versionsQuery.isPending ? <QueryLoading /> : <p className="muted">没有可显示的版本。</p>}</section>
    <section className="detail-section" aria-labelledby="request-title"><div className="detail-heading"><h2 id="request-title">运行请求</h2><p>Prefect 参数与标签，只读展示。</p></div><pre className="request-code">{JSON.stringify({ parameters: detail.parameters, tags: detail.tags }, null, 2)}</pre></section>
    {cancelMutation.isError && <div className="command-error persistent-command-error" role="alert">取消请求未获得权威回执；运行状态保持原样，没有自动重试。</div>}
    <ConfirmDialog open={cancelOpen} title={`取消运行 ${run.name}`} confirmLabel="确认取消" onClose={() => setCancelOpen(false)} onConfirm={cancelRun} busy={cancelMutation.isPending} destructive>Prefect 是唯一执行状态源。确认后仍需等待 Prefect 返回 Cancelling 或 Cancelled。</ConfirmDialog>
  </article>;
}
