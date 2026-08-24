import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { Page, RunSummary } from "../api/types";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip } from "../components/EnvelopeState";
import { ExecutionMark, ScientificMark } from "../components/StatusMark";
import { scientificReviewPath } from "../scientificReview";

export function ReviewsPage() {
  const query = useQuery({ queryKey: ["reviews", "unreviewed"], queryFn: () => api.get<Page<RunSummary>>("/api/v1/runs?scientificStatus=unreviewed") });
  return <section className="page reviews-page">
    <header className="page-header page-header--split"><div><p className="page-kicker">Review / 03</p><h1>科研结果评审</h1><p className="lede">队列只收录最新、有效且标记为 unreviewed 的 RunResult。先打开证据，再在运行详情提交 accepted / rejected / inconclusive；列表页不能一键判断。</p></div>{query.data?.data && <span className="queue-count"><strong>{query.data.data.items.length}</strong> 待判断</span>}</header>
    {query.isPending && <QueryLoading />}
    {query.isError && <QueryFailure title="评审队列暂不可用" />}
    {query.data?.data && <><SourceStrip sources={query.data.sources} /><EnvelopeErrors errors={query.data.errors} /><div className="review-stack">{query.data.data.items.map((run, index) => <article className="review-record" key={run.runId}><div className="review-index">{String(index + 1).padStart(2, "0")}</div><div className="review-body"><div className="review-title"><div><p>{run.deploymentName ?? "未注册 Deployment"}</p><h2>{run.name}</h2></div><ScientificMark status={run.scientific?.scientificStatus} /></div><div className="review-facts"><ExecutionMark type={run.state.type} name={run.state.name} /><span>{run.scientific?.artifactId}</span><span>{run.workPoolName} / {run.workQueueName}</span></div>{run.state.terminal && run.state.type !== "COMPLETED" && <p className="execution-warning">执行未正常完成，但存在可评审的 RunResult。</p>}<Link className="primary-action" to={scientificReviewPath(run.runId)}>查看证据并判断</Link></div></article>)}</div>{query.data.data.items.length === 0 && <div className="empty-state"><strong>当前没有待评审结果</strong><span>科研判断不会由执行状态自动生成。</span></div>}</>}
  </section>;
}
