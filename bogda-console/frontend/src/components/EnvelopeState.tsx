import type { ApiError, SourceMeta } from "../api/types";
import { SourceNotice } from "./SourceNotice";

const sourceNames: Record<string, string> = {
  prefect: "Prefect",
  runResult: "RunResult Artifact",
  power: "Power Agent",
};

export function SourceStrip({ sources }: { sources: Record<string, SourceMeta> }) {
  return (
    <div className="source-strip" aria-label="数据来源">
      {Object.entries(sources).map(([key, meta]) => <SourceNotice key={key} name={sourceNames[key] ?? key} meta={meta} />)}
    </div>
  );
}

export function EnvelopeErrors({ errors }: { errors: ApiError[] }) {
  if (!errors.length) return null;
  return (
    <div className="source-errors" role="status">
      {errors.map((error) => <p key={`${error.source}:${error.code}`}><strong>{sourceNames[error.source] ?? error.source} 暂不可用</strong><span>{error.message}</span></p>)}
    </div>
  );
}

export function QueryFailure({ title = "暂时无法读取数据" }: { title?: string }) {
  return <div className="state-panel state-panel--error" role="alert"><strong>{title}</strong><p>保留当前判断，不以空数据替代来源故障。</p></div>;
}

export function QueryLoading() {
  return <div className="state-panel" role="status"><span className="loading-rule" aria-hidden="true" />正在读取权威来源…</div>;
}
