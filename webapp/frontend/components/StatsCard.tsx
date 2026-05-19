interface Props {
  label: string;
  value: number | string;
  icon: string;
  color?: string;
}

export default function StatsCard({ label, value, icon, color = "accent" }: Props) {
  const colorMap: Record<string, string> = {
    accent: "text-accent border-accent/30",
    success: "text-success border-success/30",
    warning: "text-warning border-warning/30",
    danger: "text-danger border-danger/30",
    critical: "text-critical border-critical/30",
  };
  const cls = colorMap[color] || colorMap.accent;

  return (
    <div className={`bg-bg-secondary border rounded-xl p-5 ${cls}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-2xl">{icon}</span>
      </div>
      <p className="text-3xl font-bold mb-1">{value}</p>
      <p className="text-sm text-text-secondary">{label}</p>
    </div>
  );
}
