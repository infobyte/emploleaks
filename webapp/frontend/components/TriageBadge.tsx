import { Circle } from "lucide-react";

const STYLES: Record<string, { dot: string; text: string }> = {
  pending: { dot: "text-yellow-400", text: "text-yellow-400" },
  verified: { dot: "text-green-400", text: "text-green-400" },
  not_working: { dot: "text-gray-400", text: "text-gray-400" },
  false_positive: { dot: "text-red-400", text: "text-red-400" },
};

const LABELS: Record<string, string> = {
  pending: "Pending",
  verified: "Verified",
  not_working: "Not Working",
  false_positive: "False Positive",
};

interface Props {
  status: string;
  onChange?: (status: string) => void;
}

export default function TriageBadge({ status, onChange }: Props) {
  const s = STYLES[status] || STYLES.pending;

  if (onChange) {
    return (
      <select
        value={status}
        onChange={(e) => onChange(e.target.value)}
        className="text-xs px-2 py-1 rounded-md border border-border bg-bg-tertiary text-text-primary cursor-pointer appearance-none focus:outline-none focus:border-accent"
      >
        <option value="pending">Pending</option>
        <option value="verified">Verified</option>
        <option value="not_working">Not Working</option>
        <option value="false_positive">False Positive</option>
      </select>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <Circle className={`w-2 h-2 fill-current ${s.dot}`} />
      <span className={s.text}>{LABELS[status] || status}</span>
    </span>
  );
}
