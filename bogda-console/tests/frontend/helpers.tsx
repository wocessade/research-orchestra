import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { App } from "../../frontend/src/app/App";

export type JsonValue = Record<string, unknown>;
export type RouteHandler = JsonValue | ((request: { url: URL; init?: RequestInit }) => JsonValue | Response | Promise<JsonValue | Response>);

export const sourceFresh = {
  source: "prefect",
  sourceMode: "mock",
  observedAt: "2026-08-24T08:29:58Z",
  receivedAt: "2026-08-24T08:30:00Z",
  lastSuccessfulAt: "2026-08-24T08:29:58Z",
  staleAfterSeconds: 60,
  freshness: "fresh",
};

export const sourceStale = {
  ...sourceFresh,
  observedAt: "2026-08-24T09:20:00Z",
  receivedAt: "2026-08-24T09:30:00Z",
  lastSuccessfulAt: "2026-08-24T09:20:02Z",
  freshness: "stale",
};

export const completedRun = {
  runId: "run-completed-unreviewed",
  name: "alpine assay / snowline",
  deploymentId: "deployment-dorm",
  deploymentName: "alpine-assay",
  projectId: "bogda-main",
  workPoolName: "dorm-x86",
  workQueueName: "cpu",
  state: {
    type: "COMPLETED",
    name: "Completed",
    timestamp: "2026-08-24T07:44:00Z",
    terminal: true,
    message: null,
  },
  scheduledAt: "2026-08-24T07:30:00Z",
  startedAt: "2026-08-24T07:31:00Z",
  endedAt: "2026-08-24T07:44:00Z",
  scientific: {
    availability: "available",
    artifactId: "artifact-completed-1",
    artifactCreatedAt: "2026-08-24T07:44:10Z",
    scientificStatus: "unreviewed",
    reviewSummary: null,
    validationIssues: [],
  },
  commandVersion: "version-completed",
};

export const validResult = {
  availability: "available",
  artifactId: "artifact-completed-1",
  artifactCreatedAt: "2026-08-24T07:44:10Z",
  validationIssues: [],
  result: {
    run_id: "run-completed-unreviewed",
    job_id: "job-completed",
    execution_status: "Completed",
    scientific_status: "unreviewed",
    started_at: "2026-08-24T07:31:00Z",
    finished_at: "2026-08-24T07:44:00Z",
    executor: "shell",
    attempt: 1,
    declared_artifacts: [
      { uri: "file:///attempt/result.json", kind: "json", exists: true, sizeBytes: 2840 },
    ],
    summary: "Declared result exists",
    review_summary: null,
  },
};

export function envelope(data: unknown, sources: JsonValue = { prefect: sourceFresh }, errors: unknown[] = []) {
  return { data, sources, errors };
}

export function standardRoutes(): Record<string, RouteHandler> {
  return {
    "/api/v1/capabilities": envelope({ profile: "mock-all", projectId: "bogda-main", effectiveAutonomyMode: "supervised", canSubmitRegisteredDeployment: true, canCancelRun: true, canPauseSchedule: true, canPauseWorkQueue: true, canReviewScientificResult: true, canSetAutonomyMode: false, canResolveModelDecision: true, canSetModelPolicy: false, canPreparePaidRun: false }, {}),
    "/api/v1/autonomy-policy": envelope({ globalDefault: "supervised", projectOverrides: {}, revision: 0 }, {}),
    "/api/v1/overview": envelope({
      execution: {
        countsByPrefectType: { RUNNING: 1, COMPLETED: 1 },
        recentRuns: [completedRun],
      },
      science: {
        countsByScientificStatus: { unreviewed: 1 },
        attentionRuns: [completedRun],
      },
      infrastructure: {
        piService: { name: "pi-service", status: "READY", isPaused: false, concurrencyLimit: 1, activeSlots: 0, queues: [], workers: [] },
        dormX86: { name: "dorm-x86", status: "READY", isPaused: false, concurrencyLimit: 1, activeSlots: 1, queues: [], workers: [] },
      },
      power: { host: "dorm-x86", mode: "compute", agentReachable: true, sleepInhibited: true, lastTransitionAt: "2026-08-24T08:19:30Z" },
    }, { prefect: sourceFresh, runResult: { ...sourceFresh, source: "runResult" }, power: { ...sourceFresh, source: "power", sourceMode: "mock" } }),
    "/api/v1/runs": envelope({ items: [completedRun], nextCursor: null }, { prefect: sourceFresh, runResult: { ...sourceFresh, source: "runResult" } }),
    "/api/v1/infrastructure": envelope({ pools: [
      { name: "pi-service", status: "READY", isPaused: false, concurrencyLimit: 1, activeSlots: 0, queues: [{ queueId: "queue-service", name: "default", status: "READY", isPaused: false, concurrencyLimit: 1, commandVersion: "queue-service-v1" }], workers: [{ workerId: "worker-pi", name: "pi-service", status: "ONLINE", lastHeartbeatTime: "2026-08-24T08:29:55Z" }] },
      { name: "dorm-x86", status: "READY", isPaused: false, concurrencyLimit: 1, activeSlots: 1, queues: [{ queueId: "queue-cpu", name: "cpu", status: "READY", isPaused: false, concurrencyLimit: null, commandVersion: "queue-cpu-v1" }, { queueId: "queue-gpu", name: "gpu", status: "NOT_READY", isPaused: false, concurrencyLimit: null, commandVersion: "queue-gpu-v1" }], workers: [{ workerId: "worker-dorm", name: "dorm-x86", status: "ONLINE", lastHeartbeatTime: "2026-08-24T08:29:52Z" }] },
    ], dormPower: { host: "dorm-x86", mode: "compute", agentReachable: true, sleepInhibited: true, lastTransitionAt: "2026-08-24T08:19:30Z" } }, { prefect: sourceFresh, power: { ...sourceFresh, source: "power", sourceMode: "mock" } }),
    "/api/v1/deployments": envelope({ items: [{ deploymentId: "deployment-dorm", name: "alpine-assay", flowName: "alpine-assay", projectContext: { projectId: "bogda-main", effectiveAutonomyMode: "supervised", modeSource: "deployment-default", writable: false }, workPoolName: "dorm-x86", workQueueName: "cpu", parameterSchema: { type: "object", properties: { sample: { type: "string", title: "Sample" } }, required: ["sample"] }, allowlisted: true, schedules: [{ scheduleId: "schedule-dorm", label: "manual window", active: true, updatedAt: "2026-08-24T07:10:00Z", commandVersion: "schedule-v1" }] }], nextCursor: null }, { prefect: sourceFresh }),
    "/api/v1/runs/run-completed-unreviewed": envelope({
      run: completedRun,
      parameters: { sample: "snowline" },
      tags: ["review"],
      projectContext: { projectId: "bogda-main", effectiveAutonomyMode: "supervised", modeSource: "frozen-run-request", writable: false },
    }, { prefect: sourceFresh, runResult: { ...sourceFresh, source: "runResult" } }),
    "/api/v1/runs/run-completed-unreviewed/result": envelope(validResult, { runResult: { ...sourceFresh, source: "runResult" } }),
    "/api/v1/model-policy": envelope({
      projectId: "bogda-main", source: "global", revision: 1, inheritsGlobal: true,
      minimumRemaining: "6.00", workloadSafetyMargin: "1.25", defaultModelTier: "auto",
      allowAutoUpgrade: false, allowFlashDowngrade: true, preferOffPeak: true, autoResume: false,
      criticalNotifications: true, usageSnapshotStaleAfterSeconds: 120,
      priceCatalog: { status: "ready", version: "deepseek-v4-0813", effectiveAt: "2026-08-28T00:00:00Z", reviewBy: "2026-09-01T00:00:00Z", source: "deepseek" },
      hardSafetyBaselines: { budgetIncreaseApprovalRequired: true, decideAuditNoSilentDowngrade: true, humanExternalActions: true, humanScientificJudgment: true, minimumRemainingEnforced: true, promptArchivingRequired: true, structuredEventLog: true, unknownUsageRecoveryGate: true, usageSnapshotFailClosed: true },
    }, { modelControl: { ...sourceFresh, source: "modelControl" } }),
    "/api/v1/runs/run-completed-unreviewed/result/versions": envelope({
      items: [{ artifactId: "artifact-completed-1", createdAt: "2026-08-24T07:44:10Z", availability: "available", scientificStatus: "unreviewed", reviewSummary: null }],
      nextCursor: null,
    }, { runResult: { ...sourceFresh, source: "runResult" } }),
  };
}

export const requestLog: string[] = [];

export function installApi(routes: Record<string, RouteHandler> = standardRoutes()) {
  requestLog.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url, "http://console.test");
    requestLog.push(`${url.pathname}${url.search}`);
    const exact = routes[`${url.pathname}${url.search}`];
    const withoutSearch = routes[url.pathname];
    const handler = exact ?? withoutSearch;
    if (!handler) return new Response(JSON.stringify(envelope(null, {}, [{ code: "NOT_FOUND", message: url.pathname, source: "console", retryable: false }])), { status: 404, headers: { "Content-Type": "application/json" } });
    const body = typeof handler === "function" ? await handler({ url, init }) : handler;
    if (body instanceof Response) return body;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

export function renderAppAt(path: string, routes?: Record<string, RouteHandler>) {
  installApi(routes);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
    </QueryClientProvider>,
  );
}

export function renderWithClient(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}
