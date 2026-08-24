import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Page, RunDetail, RunResultVersion, RunResultView } from "../api/types";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip } from "../components/EnvelopeState";
import { ExecutionMark, ScientificMark } from "../components/StatusMark";

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

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const detailQuery = useQuery({ queryKey: ["run", runId], queryFn: () => api.get<RunDetail>(`/api/v1/runs/${runId}`) });
  const resultQuery = useQuery({ queryKey: ["result", runId], queryFn: () => api.get<RunResultView>(`/api/v1/runs/${runId}/result`) });
  const versionsQuery = useQuery({ queryKey: ["result-versions", runId], queryFn: () => api.get<Page<RunResultVersion>>(`/api/v1/runs/${runId}/result/versions`) });

  if (detailQuery.isPending) return <section className="page"><QueryLoading /></section>;
  if (detailQuery.isError || !detailQuery.data.data) return <section className="page"><QueryFailure title="运行详情暂不可用" /></section>;
  const envelope = detailQuery.data;
  const detail = envelope.data!;
  const run = detail.run;
  const science = run.scientific;

  return <article className="page run-detail">
    <Link className="back-link" to="/runs">← 返回运行账簿</Link>
    <header className="page-header"><p className="page-kicker">Run / {run.runId}</p><h1>{run.name}</h1><p className="lede">{run.deploymentName ?? "未注册 Deployment"} · {run.workPoolName ?? "—"} / {run.workQueueName ?? "—"}</p></header>
    <SourceStrip sources={{ ...envelope.sources, ...(resultQuery.data?.sources ?? {}) }} />
    <EnvelopeErrors errors={[...envelope.errors, ...(resultQuery.data?.errors ?? [])]} />
    <section className="authority-bands" aria-label="执行与科研状态">
      <div><p>Prefect 执行状态</p><ExecutionMark type={run.state.type} name={run.state.name} /><time dateTime={run.state.timestamp}>{formatAbsolute(run.state.timestamp)}</time></div>
      <div><p>科研判断状态</p>{science?.availability === "available" ? <ScientificMark status={science.scientificStatus} /> : <span className={`availability availability--${science?.availability ?? "none"}`}>{science?.availability === "invalid" ? "RunResult 无效" : science?.availability === "missing" ? "RunResult 缺失" : "科研状态不可用"}</span>}<span>{science?.artifactId ?? "无权威 Artifact"}</span></div>
    </section>
    <section className="detail-section context-section" aria-labelledby="context-title"><div className="detail-heading"><h2 id="context-title">Project Context</h2><p>只读上下文，为未来 C 模式预留契约，不在此修改。</p></div>{detail.projectContext ? <dl className="fact-grid"><div><dt>Project</dt><dd>{detail.projectContext.projectId}</dd></div><div><dt>有效自主模式</dt><dd>{detail.projectContext.effectiveAutonomyMode}</dd></div><div><dt>模式来源</dt><dd>{detail.projectContext.modeSource}</dd></div><div><dt>可写</dt><dd>否</dd></div></dl> : <p className="muted">Project Context 不可用。</p>}</section>
    {resultQuery.isPending && <QueryLoading />}
    {resultQuery.isError && <QueryFailure title="RunResult 暂不可用" />}
    {resultQuery.data?.data && <ResultPanel view={resultQuery.data.data} executionType={run.state.type} />}
    <section className="detail-section" aria-labelledby="versions-title"><div className="detail-heading"><h2 id="versions-title">RunResult 版本</h2><p>由新到旧；第一条是当前科研权威版本。</p></div>{versionsQuery.data?.data?.items.length ? <ol className="version-list">{versionsQuery.data.data.items.map((version, index) => <li key={version.artifactId}><span>{index === 0 ? "当前" : `历史 ${index}`}</span><strong>{version.artifactId}</strong><time dateTime={version.createdAt}>{formatAbsolute(version.createdAt)}</time><em>{version.availability}</em></li>)}</ol> : versionsQuery.isPending ? <QueryLoading /> : <p className="muted">没有可显示的版本。</p>}</section>
    <section className="detail-section" aria-labelledby="request-title"><div className="detail-heading"><h2 id="request-title">运行请求</h2><p>Prefect 参数与标签，只读展示。</p></div><pre className="request-code">{JSON.stringify({ parameters: detail.parameters, tags: detail.tags }, null, 2)}</pre></section>
  </article>;
}
