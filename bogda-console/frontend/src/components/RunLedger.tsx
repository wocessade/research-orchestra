import { Link } from "react-router-dom";

import type { RunSummary } from "../api/types";
import { ExecutionMark, ScientificMark } from "./StatusMark";

function formatAbsolute(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function ScientificCell({ run }: { run: RunSummary }) {
  const science = run.scientific;
  if (!science) return <span className="availability availability--none">未产生</span>;
  if (science.availability === "missing") return <span className="availability availability--missing">RunResult 缺失</span>;
  if (science.availability === "invalid") return <span className="availability availability--invalid">RunResult 无效</span>;
  return <ScientificMark status={science.scientificStatus} />;
}

function RunIdentity({ run }: { run: RunSummary }) {
  return <span className="run-identity"><Link to={`/runs/${run.runId}`}>{run.name}</Link><small>{run.deploymentName ?? "未注册 Deployment"} · {run.runId}</small></span>;
}

export function RunLedger({ runs, emptyText = "没有符合条件的运行" }: { runs: RunSummary[]; emptyText?: string }) {
  if (!runs.length) return <div className="empty-state"><strong>{emptyText}</strong><span>筛选条件没有匹配权威来源中的记录。</span></div>;
  return (
    <div className="run-ledger">
      <div className="run-ledger__table">
        <table aria-label="运行账簿">
          <thead><tr><th>运行</th><th>Prefect 状态</th><th>科研状态</th><th>执行位置</th><th>状态时间</th></tr></thead>
          <tbody>{runs.map((run) => (
            <tr key={run.runId}>
              <td><RunIdentity run={run} /></td>
              <td><ExecutionMark type={run.state.type} name={run.state.name} /></td>
              <td><ScientificCell run={run} /></td>
              <td><span className="route-cell"><strong>{run.workPoolName ?? "—"}</strong><small>{run.workQueueName ?? "—"}</small></span></td>
              <td><time dateTime={run.state.timestamp}>{formatAbsolute(run.state.timestamp)}</time></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="run-ledger__records">
        {runs.map((run) => (
          <article className="run-record" aria-label={`运行 ${run.name}`} key={run.runId}>
            <RunIdentity run={run} />
            <dl>
              <div><dt>Prefect 状态</dt><dd><ExecutionMark type={run.state.type} name={run.state.name} /></dd></div>
              <div><dt>科研状态</dt><dd><ScientificCell run={run} /></dd></div>
              <div><dt>执行位置</dt><dd>{run.workPoolName ?? "—"} / {run.workQueueName ?? "—"}</dd></div>
              <div><dt>状态时间</dt><dd><time dateTime={run.state.timestamp}>{formatAbsolute(run.state.timestamp)}</time></dd></div>
            </dl>
          </article>
        ))}
      </div>
    </div>
  );
}
