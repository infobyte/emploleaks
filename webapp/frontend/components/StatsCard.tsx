import { type LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: number | string;
  Icon: LucideIcon;
  color?: string;
}

const COLORS: Record<string, { icon: string; border: string; bg: string }> = {
  accent: { icon: "text-accent", border: "border-border", bg: "bg-accent/5" },
  success: { icon: "text-success", border: "border-border", bg: "bg-success/5" },
  warning: { icon: "text-warning", border: "border-border", bg: "bg-warning/5" },
  danger: { icon: "text-danger", border: "border-border", bg: "bg-danger/5" },
  critical: { icon: "text-critical", border: "border-border", bg: "bg-critical/5" },
};

export default function StatsCard({ label, value, Icon, color = "accent" }: Props) {
  const c = COLORS[color] || COLORS.accent;

  return (
    <div className={`${c.bg} border ${c.border} rounded-xl p-4 hover:border-border-light transition-colors`}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-bg-tertiary">
          <Icon className={`w-4 h-4 ${c.icon}`} />
        </div>
        <div>
          <p className="text-2xl font-semibold text-text-primary leading-none">{value}</p>
          <p className="text-xs text-text-secondary mt-1">{label}</p>
        </div>
      </div>
    </div>
  );
}
