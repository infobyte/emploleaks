const COLORS: Record<string, string> = {
  pending: "bg-yellow-900/30 text-yellow-400 border-yellow-700/50",
  verified: "bg-green-900/30 text-green-400 border-green-700/50",
  not_working: "bg-gray-800/30 text-gray-400 border-gray-600/50",
  false_positive: "bg-red-900/30 text-red-400 border-red-700/50",
};

interface Props {
  status: string;
  onChange?: (status: string) => void;
}

export default function TriageBadge({ status, onChange }: Props) {
  if (onChange) {
    return (
      <select
        value={status}
        onChange={(e) => onChange(e.target.value)}
        className={`text-xs px-2 py-1 rounded-md border cursor-pointer appearance-none bg-bg-tertiary ${
          COLORS[status] || COLORS.pending
        }`}
      >
        <option value="pending">Pending</option>
        <option value="verified">Verified</option>
        <option value="not_working">Not Working</option>
        <option value="false_positive">False Positive</option>
      </select>
    );
  }

  return (
    <span
      className={`inline-block text-xs px-2.5 py-1 rounded-full border ${
        COLORS[status] || COLORS.pending
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
