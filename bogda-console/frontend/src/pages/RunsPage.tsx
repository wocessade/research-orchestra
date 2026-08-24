import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Page, RunSummary } from "../api/types";
import { EnvelopeErrors, QueryFailure, QueryLoading, SourceStrip } from "../components/EnvelopeState";
import { RunLedger } from "../components/RunLedger";

const executionOptions = ["SCHEDULED", "RUNNING", "COMPLETED", "FAILED", "CRASHED", "CANCELLED"];
const scienceOptions = ["unreviewed", "accepted", "rejected", "inconclusive"];

export function RunsPage() {
  const [executionType, setExecutionType] = useState("");
  const [scientificStatus, setScientificStatus] = useState("");
  const params = new URLSearchParams();
  if (executionType) params.set("executionType", executionType);
  if (scientificStatus) params.set("scientificStatus", scientificStatus);
  const suffix = params.toString();
  const path = `/api/v1/runs${suffix ? `?${suffix}` : ""}`;
  const query = useQuery({ queryKey: ["runs", executionType, scientificStatus], queryFn: () => api.get<Page<RunSummary>>(path) });

  return (
    <section className="page">
      <header className="page-header"><p className="page-kicker">Ledger / 02</p><h1>运行账簿</h1><p className="lede">原样保留 Prefect state name，并把科研评审状态放在独立一列。</p></header>
      <form className="filter-bar" aria-label="运行筛选" onSubmit={(event) => event.preventDefault()}>
        <label>执行状态<select value={executionType} onChange={(event) => setExecutionType(event.target.value)}><option value="">全部</option>{executionOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>科研状态<select value={scientificStatus} onChange={(event) => setScientificStatus(event.target.value)}><option value="">全部</option>{scienceOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      </form>
      {query.isPending && <QueryLoading />}
      {query.isError && <QueryFailure title="Prefect 运行数据暂不可用" />}
      {query.data?.data && <>
        <SourceStrip sources={query.data.sources} />
        <EnvelopeErrors errors={query.data.errors} />
        <div className="ledger-meta"><span>{query.data.data.items.length} 个运行</span><span>状态以来源观测时间为准</span></div>
        <RunLedger runs={query.data.data.items} />
      </>}
    </section>
  );
}
