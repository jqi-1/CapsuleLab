export default function MetricCard({
  label,
  value,
  sub,
  active = false,
  accent = "amber",
}: {
  label: string;
  value: string | React.ReactNode;
  sub?: string;
  active?: boolean;
  accent?: "amber" | "teal" | "pink";
}) {
  const accentClass = active ? "metric-active" : accent === "pink" || accent === "amber" ? "metric-warn" : "";

  return (
    <div className={`metric ${accentClass}`}>
      <div className="eyebrow">{label}</div>
      <div className="mt-3 min-w-0 text-2xl font-black leading-none text-[var(--ink)]">
        {value}
      </div>
      {sub && <div className="mt-2 truncate text-sm text-[var(--muted)]">{sub}</div>}
    </div>
  );
}
