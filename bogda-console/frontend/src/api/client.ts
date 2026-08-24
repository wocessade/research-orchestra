import type { ApiError, Envelope } from "./types";

export class ApiClientError extends Error {
  readonly status: number;
  readonly errors: ApiError[];
  readonly envelope: Envelope<unknown>;

  constructor(status: number, envelope: Envelope<unknown>) {
    super(envelope.errors[0]?.message ?? `HTTP ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.errors = envelope.errors;
    this.envelope = envelope;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<Envelope<T>> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const envelope = await response.json() as Envelope<T>;
  if (!response.ok) throw new ApiClientError(response.status, envelope as Envelope<unknown>);
  return envelope;
}

export const api = {
  get<T>(path: string): Promise<Envelope<T>> {
    return request<T>(path);
  },
  command<T>(path: string, body: unknown): Promise<Envelope<T>> {
    return request<T>(path, { method: "POST", body: JSON.stringify(body) });
  },
};
