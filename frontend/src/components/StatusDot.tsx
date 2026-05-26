type Status = "alive" | "running" | "stopped" | "dead" | "building" | "starting" | "stopping";

const statusConfig: Record<Status, { dot: string; label: string }> = {
  alive: { dot: "status-live", label: "Alive" },
  running: { dot: "status-live", label: "Running" },
  stopped: { dot: "status-stop", label: "Stopped" },
  dead: { dot: "status-dead", label: "Offline" },
  building: { dot: "status-live", label: "Building" },
  starting: { dot: "status-live", label: "Starting" },
  stopping: { dot: "status-dead", label: "Stopping" },
};

export default function StatusDot({
  status,
  label,
}: {
  status: Status;
  label?: string;
  pulse?: boolean;
}) {
  const cfg = statusConfig[status];

  return (
    <span className="status-pill" title={label ?? cfg.label}>
      <span className={`status-dot ${cfg.dot}`} />
      {label ?? cfg.label}
    </span>
  );
}
