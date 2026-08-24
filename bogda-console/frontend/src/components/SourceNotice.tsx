import type { SourceMeta } from "../api/types";


export function SourceNotice({ name, meta }: { name: string; meta: SourceMeta }) {
  const stale = meta.freshness !== "fresh";
  return (
    <div className={`source-notice ${stale ? "source-notice--attention" : ""}`} role={stale ? "status" : undefined}>
      <span aria-hidden="true">{stale ? "△" : "●"}</span>
      <span>{name} · {meta.freshness === "fresh" ? "实时" : meta.freshness === "stale" ? "陈旧数据" : "不可用"}</span>
      {meta.sourceMode === "mock" && <strong>模拟数据</strong>}
      <time dateTime={meta.observedAt ?? undefined}>{meta.observedAt ? new Date(meta.observedAt).toLocaleString("zh-CN", { hour12: false }) : "无观测时间"}</time>
    </div>
  );
}
