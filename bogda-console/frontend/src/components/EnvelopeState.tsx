import type { ApiError, Envelope, SourceMeta } from "../api/types";
import { SourceNotice } from "./SourceNotice";

export function envelopeHasErrors(envelope: Envelope<unknown> | undefined | null) {
  return Boolean(envelope?.errors.length);
}

export function envelopeHasNonFreshSources(envelope: Envelope<unknown> | undefined | null) {
  return Object.values(envelope?.sources ?? {}).some((source) => source.freshness !== "fresh");
}

const sourceNames: Record<string, string> = {
  prefect: "Prefect",
  runResult: "RunResult Artifact",
  power: "Power Agent",
  modelControl: "模型控制",
  usageBalance: "账户余额",
  autonomyPolicy: "科研自主策略",
};

export function SourceStrip({ sources }: { sources: Record<string, SourceMeta> }) {
  const entries = Object.entries(sources);
  if (!entries.length) return null;
  return (
    <div className="source-strip" role="group" aria-label="数据来源">
      {entries.map(([key, meta]) => <SourceNotice key={key} name={sourceNames[key] ?? key} meta={meta} />)}
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
