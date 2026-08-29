import type { components } from "./generated";

export type Schemas = components["schemas"];
export type SourceMeta = Schemas["SourceMeta"];
export type ApiError = Schemas["ApiError"];
export type RunSummary = Schemas["RunSummary"];
export type RunDetail = Schemas["RunDetail"];
export type RunResultView = Schemas["RunResultView"];
export type RunResultVersion = Schemas["RunResultVersionSummary"];
export type DeploymentSummary = Schemas["DeploymentSummary"];
export type InfrastructureView = Schemas["InfrastructureView"];
export type OverviewSnapshot = Schemas["OverviewSnapshot"];
export type CapabilitySnapshot = Schemas["CapabilitySnapshot"];
export type AutonomyMode = "manual" | "supervised" | "autonomous";
export type AutonomyPolicySnapshot = {
  globalDefault: AutonomyMode;
  projectOverrides: Record<string, AutonomyMode>;
  revision: number;
};
export type QueueSnapshot = Schemas["QueueSnapshot"];
export type PoolSnapshot = Schemas["PoolSnapshot"];
export type DecisionAction = Schemas["DecisionAction"];
export type DecisionItem = Schemas["DecisionItem"];
export type DecisionCenterSnapshot = Schemas["DecisionCenterSnapshot"];
export type DecisionRequest = Schemas["DecisionRequest"];

export interface Envelope<T> {
  data: T | null;
  sources: Record<string, SourceMeta>;
  errors: ApiError[];
}

export interface Page<T> {
  items: T[];
  nextCursor?: string | null;
}

export interface CommandReceipt<T> {
  command: string;
  resourceId: string;
  acceptedAt: string;
  snapshot: T;
}
