const scienceLabels: Record<string, string> = {
  unreviewed: "待评审",
  accepted: "已接受",
  rejected: "已拒绝",
  inconclusive: "无定论",
};

export function ExecutionMark({ type, name }: { type: string; name: string }) {
  return <span className={`status-mark execution execution--${type.toLowerCase()}`}><i aria-hidden="true" />{name}<small>{type}</small></span>;
}

export function ScientificMark({ status }: { status: string | null | undefined }) {
  const value = status ?? "unreviewed";
  return <span className={`status-mark science science--${value}`}><i aria-hidden="true" />{scienceLabels[value] ?? value}</span>;
}
