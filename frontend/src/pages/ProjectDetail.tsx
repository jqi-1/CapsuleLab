import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  appLogs,
  AppStatus,
  buildProject,
  collectResourceSnapshot,
  composeDown,
  composeLogs,
  composeUp,
  getProject,
  getResourceHistory,
  projectBuildLogs,
  projectDoctor,
  projectLogs,
  projectStatus,
  startApp,
  startProject,
  stopApp,
  stopProject,
  BuildLogEntry,
  DoctorReport,
  ProjectDetail as ProjectDetailType,
  ProjectStatus,
  ResourceSnapshot,
} from "../api";
import LogViewer from "../components/LogViewer";
import MetricCard from "../components/MetricCard";
import StatusDot from "../components/StatusDot";
import {
  ActivityIcon,
  AlertIcon,
  CheckIcon,
  ExternalIcon,
  HammerIcon,
  PlayIcon,
  RefreshIcon,
  StopIcon,
  TerminalIcon,
} from "../components/icons";

type Action = "idle" | "building" | "starting" | "stopping";
type Tab = "overview" | "apps" | "resources" | "diagnostics" | "logs";

const tabs: Tab[] = ["overview", "apps", "resources", "diagnostics", "logs"];

function percent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(100, value));
}

function formatPercent(value: number | null | undefined) {
  const p = percent(value);
  return p === null ? "N/A" : `${p.toFixed(1)}%`;
}

function formatMb(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(0)} MB`;
}

function Meter({ value }: { value: number | null | undefined }) {
  const p = percent(value);
  return (
    <div className="meter mt-2">
      <div className="meter-fill" style={{ width: `${p ?? 0}%` }} />
    </div>
  );
}

function ActionButton({
  label,
  icon,
  loading,
  onClick,
  variant = "primary",
}: {
  label: string;
  icon: React.ReactNode;
  loading: boolean;
  onClick: () => void;
  variant?: "primary" | "danger" | "ghost";
}) {
  const className = variant === "danger" ? "danger-button" : variant === "ghost" ? "ghost-button" : "command-button";
  return (
    <button onClick={onClick} disabled={loading} className={className}>
      {loading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : icon}
      {label}
    </button>
  );
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ProjectDetailType | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<ProjectStatus | null>(null);
  const [appStatuses, setAppStatuses] = useState<Record<string, AppStatus>>({});
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [action, setAction] = useState<Action>("idle");
  const [appLoading, setAppLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState("");
  const [logsLoading, setLogsLoading] = useState(false);
  const [openAppLogs, setOpenAppLogs] = useState<Record<string, boolean>>({});
  const [appLogsData, setAppLogsData] = useState<Record<string, string>>({});
  const [appLogsLoading, setAppLogsLoading] = useState<string | null>(null);
  const [composeLoading, setComposeLoading] = useState(false);
  const [composeLogsText, setComposeLogsText] = useState("");
  const [doctorReport, setDoctorReport] = useState<DoctorReport | null>(null);
  const [doctorLoading, setDoctorLoading] = useState(false);
  const [buildLogsHistory, setBuildLogsHistory] = useState<BuildLogEntry[]>([]);
  const [buildLogsLoading, setBuildLogsLoading] = useState(false);
  const [resourceHistory, setResourceHistory] = useState<ResourceSnapshot[]>([]);
  const [resourceLoading, setResourceLoading] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    try {
      setDetail(await getProject(id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load project");
    }
  }, [id]);

  const fetchRuntimeStatus = useCallback(async () => {
    if (!id) return;
    try {
      const status = await projectStatus(id);
      setRuntimeStatus(status);
      setAppStatuses(Object.fromEntries(status.apps.map((app) => [app.app_id, app])));
    } catch {
      /* keep previous status visible */
    }
  }, [id]);

  const fetchLogs = useCallback(async () => {
    if (!id) return;
    setLogsLoading(true);
    try {
      const output = await projectLogs(id, 80);
      setLogs(output.logs);
    } catch {
      setLogs("Failed to load container logs.");
    } finally {
      setLogsLoading(false);
    }
  }, [id]);

  const fetchResourceHistory = useCallback(async () => {
    if (!id) return;
    setResourceLoading(true);
    try {
      const historyData = await getResourceHistory(id, 50);
      setResourceHistory(historyData.history);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load resource history");
    } finally {
      setResourceLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
    fetchRuntimeStatus();
  }, [fetchDetail, fetchRuntimeStatus]);

  useEffect(() => {
    if (runtimeStatus?.container_running || detail?.container_running) {
      const interval = setInterval(fetchRuntimeStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [detail?.container_running, fetchRuntimeStatus, runtimeStatus?.container_running]);

  useEffect(() => {
    if (activeTab === "resources" && resourceHistory.length === 0) fetchResourceHistory();
    if (activeTab === "logs" && !logs) fetchLogs();
  }, [activeTab, fetchLogs, fetchResourceHistory, logs, resourceHistory.length]);

  const running = runtimeStatus?.container_running ?? detail?.container_running ?? false;
  const apps = useMemo(() => detail?.config.apps ?? [], [detail]);

  async function handleBuild() {
    if (!id) return;
    setAction("building");
    setError(null);
    try {
      await buildProject(id);
      await fetchDetail();
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Build failed");
    } finally {
      setAction("idle");
    }
  }

  async function handleStart() {
    if (!id) return;
    setAction("starting");
    setError(null);
    try {
      await startProject(id);
      await fetchDetail();
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Start failed");
    } finally {
      setAction("idle");
    }
  }

  async function handleStop() {
    if (!id) return;
    setAction("stopping");
    setError(null);
    try {
      await stopProject(id);
      await fetchDetail();
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Stop failed");
    } finally {
      setAction("idle");
    }
  }

  async function handleStartApp(appId: string) {
    if (!id) return;
    setAppLoading(appId);
    setError(null);
    try {
      await startApp(id, appId);
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Failed to start ${appId}`);
    } finally {
      setAppLoading(null);
    }
  }

  async function handleStopApp(appId: string) {
    if (!id) return;
    setAppLoading(appId);
    setError(null);
    try {
      await stopApp(id, appId);
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Failed to stop ${appId}`);
    } finally {
      setAppLoading(null);
    }
  }

  async function toggleAppLogs(appId: string) {
    if (openAppLogs[appId]) {
      setOpenAppLogs((prev) => ({ ...prev, [appId]: false }));
      return;
    }
    setOpenAppLogs((prev) => ({ ...prev, [appId]: true }));
    if (!id || appLogsData[appId]) return;
    setAppLogsLoading(appId);
    try {
      const output = await appLogs(id, appId, 40);
      setAppLogsData((prev) => ({ ...prev, [appId]: output.logs }));
    } catch {
      setAppLogsData((prev) => ({ ...prev, [appId]: "Failed to load app logs." }));
    } finally {
      setAppLogsLoading(null);
    }
  }

  async function handleComposeUp() {
    if (!id) return;
    setComposeLoading(true);
    setError(null);
    try {
      await composeUp(id, true);
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start Compose services");
    } finally {
      setComposeLoading(false);
    }
  }

  async function handleComposeDown() {
    if (!id) return;
    setComposeLoading(true);
    setError(null);
    try {
      await composeDown(id);
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to stop Compose services");
    } finally {
      setComposeLoading(false);
    }
  }

  async function handleComposeLogs() {
    if (!id) return;
    setComposeLoading(true);
    try {
      const output = await composeLogs(id, 80);
      setComposeLogsText(output.logs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load Compose logs");
    } finally {
      setComposeLoading(false);
    }
  }

  async function handleDoctor() {
    if (!id) return;
    setDoctorLoading(true);
    try {
      setDoctorReport(await projectDoctor(id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Doctor check failed");
    } finally {
      setDoctorLoading(false);
    }
  }

  async function handleBuildLogs() {
    if (!id) return;
    setBuildLogsLoading(true);
    try {
      setBuildLogsHistory(await projectBuildLogs(id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load build history");
    } finally {
      setBuildLogsLoading(false);
    }
  }

  async function handleCollectResources() {
    if (!id) return;
    setResourceLoading(true);
    try {
      await collectResourceSnapshot(id);
      await fetchResourceHistory();
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to collect resources");
    } finally {
      setResourceLoading(false);
    }
  }

  if (!detail) {
    return (
      <div className="page-pad">
        <div className="flex items-center gap-3 font-mono text-sm text-[var(--muted)]">
          <RefreshIcon className="h-4 w-4 animate-spin" />
          {error || "loading project"}
        </div>
      </div>
    );
  }

  return (
    <div className="page-pad">
      <section className="border-b border-[rgba(24,26,31,0.16)] pb-6">
        <div className="flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
          <Link to="/" className="font-bold hover:text-[var(--ink)]">Projects</Link>
          <span>/</span>
          <span className="font-mono">{detail.config.name}</span>
        </div>
        <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <div className="mb-4">
              <StatusDot status={running ? "running" : "stopped"} label={running ? "Runtime running" : "Runtime stopped"} />
            </div>
            <h1 className="section-title truncate">{detail.config.name}</h1>
            {detail.config.description && <p className="mt-4 max-w-3xl text-lg text-[var(--muted)]">{detail.config.description}</p>}
            <p className="mt-3 truncate font-mono text-sm text-[var(--muted)]">{detail.path}</p>
          </div>
          <div className="flex flex-wrap items-start gap-2 lg:pt-8">
            <ActionButton label="Build" icon={<HammerIcon />} loading={action === "building"} onClick={handleBuild} variant="ghost" />
            {running ? (
              <ActionButton label="Stop" icon={<StopIcon />} loading={action === "stopping"} onClick={handleStop} variant="danger" />
            ) : (
              <ActionButton label="Start" icon={<PlayIcon />} loading={action === "starting"} onClick={handleStart} />
            )}
          </div>
        </div>
      </section>

      {error && (
        <div className="my-6 flex items-start gap-3 border border-[rgba(182,75,61,0.35)] bg-[rgba(182,75,61,0.08)] p-4 text-sm text-[var(--coral)]">
          <AlertIcon className="mt-0.5 h-4 w-4 flex-none" />
          <span className="font-mono">{error}</span>
        </div>
      )}

      {runtimeStatus?.readiness.warnings.length ? (
        <div className="my-6 flex items-start gap-3 border border-[rgba(164,105,42,0.35)] bg-[rgba(164,105,42,0.08)] p-4 text-sm text-[var(--brass)]">
          <AlertIcon className="mt-0.5 h-4 w-4 flex-none" />
          <span className="font-mono">{runtimeStatus.readiness.warnings.join(" | ")}</span>
        </div>
      ) : null}

      <div className="grid gap-3 py-6 md:grid-cols-4">
        <MetricCard label="Container" value={running ? "Running" : "Stopped"} active={running} accent={running ? "teal" : "amber"} />
        <MetricCard label="Image" value={detail.config.runtime.image.split(":")[0]} sub={detail.config.runtime.image} />
        <MetricCard
          label="GPU"
          value={detail.config.runtime.gpu ? (runtimeStatus?.gpu_available ? "Available" : "Requested") : "Disabled"}
          sub={runtimeStatus?.gpu_name || undefined}
          active={Boolean(runtimeStatus?.gpu_available)}
          accent="pink"
        />
        <MetricCard label="Runtime" value={detail.config.runtime.type} sub={`Dockerfile: ${detail.config.runtime.dockerfile}`} />
      </div>

      <div className="flex gap-5 overflow-x-auto border-b border-[rgba(24,26,31,0.16)]">
        {tabs.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`tab-button ${activeTab === tab ? "tab-button-active" : ""}`}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <section className="grid gap-4 py-6 lg:grid-cols-3">
          <div className="panel p-5">
            <div className="eyebrow">git</div>
            <div className="mt-4 space-y-2 font-mono text-sm">
              <div>{runtimeStatus?.git.is_repo ? runtimeStatus.git.branch || "detached HEAD" : "Not a Git repo"}</div>
              <div className="truncate text-[var(--muted)]">{runtimeStatus?.git.remote || "No remote"}</div>
              <div className={runtimeStatus?.git.dirty_files ? "text-[var(--brass)]" : "text-[var(--muted)]"}>
                {runtimeStatus?.git.dirty_files ?? 0} dirty files
              </div>
            </div>
          </div>
          <div className="panel p-5">
            <div className="eyebrow">resources</div>
            <div className="mt-4 space-y-2 font-mono text-sm">
              <div>{runtimeStatus?.resources.disk.free_percent ?? "N/A"}% disk free</div>
              <div>{runtimeStatus?.resources.gpu.available ? `${runtimeStatus.resources.gpu.gpus.length} GPU detected` : "GPU unavailable"}</div>
              <div className="truncate text-[var(--muted)]">{runtimeStatus?.resources.disk.path || "No disk path"}</div>
            </div>
          </div>
          <div className="panel p-5">
            <div className="eyebrow">reproducibility</div>
            <div className="mt-4 space-y-2 font-mono text-sm">
              <div>{runtimeStatus?.build ? runtimeStatus.build.built_at : "No build metadata"}</div>
              <div className={runtimeStatus?.secrets.missing.length ? "text-[var(--brass)]" : "text-[var(--muted)]"}>
                {runtimeStatus?.secrets.missing.length ? `Missing: ${runtimeStatus.secrets.missing.join(", ")}` : "Required secrets present"}
              </div>
              <div>{runtimeStatus?.git.lfs_available ? "Git LFS available" : "Git LFS optional"}</div>
            </div>
          </div>
        </section>
      )}

      {activeTab === "apps" && (
        <section className="py-6">
          <div className="panel p-5">
            {apps.length === 0 ? (
              <div className="py-10 text-center text-[var(--muted)]">No applications configured.</div>
            ) : (
              apps.map((app) => {
                const status = appStatuses[app.id];
                const alive = status?.alive;
                const loading = appLoading === app.id;
                const url = status?.url || (app.port !== null ? `http://localhost:${app.port}${app.url_path}` : "#");
                return (
                  <div key={app.id} className="data-row">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <StatusDot status={alive === true ? "alive" : alive === false ? "dead" : "stopped"} />
                        <h2 className="text-xl font-black">{app.name}</h2>
                        {app.port !== null && <span className="font-mono text-sm text-[var(--muted)]">:{app.port}</span>}
                        <span className="font-mono text-sm text-[var(--muted)]">{app.url_path}</span>
                      </div>
                      {status?.pid && <div className="mt-2 font-mono text-sm text-[var(--muted)]">PID {status.pid}</div>}
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <button onClick={() => toggleAppLogs(app.id)} className="ghost-button">
                        <TerminalIcon />
                        Logs
                      </button>
                      <button onClick={() => handleStartApp(app.id)} disabled={loading || !running} className="command-button">
                        {loading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <PlayIcon />}
                        Start
                      </button>
                      <button onClick={() => handleStopApp(app.id)} disabled={loading || !running} className="ghost-button">
                        <StopIcon />
                        Stop
                      </button>
                      <a href={url} target="_blank" rel="noreferrer" className="ghost-button">
                        <ExternalIcon />
                        Open
                      </a>
                    </div>
                    {openAppLogs[app.id] && (
                      <div className="col-span-full">
                        <LogViewer logs={appLogsData[app.id] || ""} loading={appLogsLoading === app.id} />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {runtimeStatus?.compose.detected && (
            <div className="panel mt-5 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="eyebrow">compose</div>
                  <div className="mt-2 font-mono text-sm text-[var(--muted)]">
                    {runtimeStatus.compose.compose_file} | {runtimeStatus.compose.binary || "unavailable"}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={handleComposeLogs} disabled={composeLoading} className="ghost-button">
                    <TerminalIcon />
                    Logs
                  </button>
                  <button onClick={handleComposeUp} disabled={composeLoading || !runtimeStatus.compose.available} className="command-button">
                    <PlayIcon />
                    Up
                  </button>
                  <button onClick={handleComposeDown} disabled={composeLoading || !runtimeStatus.compose.available} className="ghost-button">
                    <StopIcon />
                    Down
                  </button>
                </div>
              </div>
              <div className="mt-5 divide-y divide-[rgba(24,26,31,0.12)]">
                {runtimeStatus.compose.services.length ? runtimeStatus.compose.services.map((service, index) => (
                  <div key={`${service.name}-${index}`} className="flex flex-wrap justify-between gap-3 py-3">
                    <span className="font-black">{service.service || service.name}</span>
                    <span className="font-mono text-sm text-[var(--muted)]">
                      {service.state || "unknown"} {typeof service.ports === "string" ? service.ports : ""}
                    </span>
                  </div>
                )) : (
                  <div className="py-6 font-mono text-sm text-[var(--muted)]">{runtimeStatus.compose.error || "No Compose services are running."}</div>
                )}
              </div>
              {composeLogsText && <div className="mt-4"><LogViewer logs={composeLogsText} loading={composeLoading} /></div>}
            </div>
          )}
        </section>
      )}

      {activeTab === "resources" && (
        <section className="space-y-5 py-6">
          <div className="flex flex-wrap gap-2">
            <button onClick={handleCollectResources} disabled={resourceLoading} className="command-button">
              {resourceLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <ActivityIcon />}
              Collect
            </button>
            <button onClick={fetchResourceHistory} disabled={resourceLoading} className="ghost-button">
              <RefreshIcon />
              Refresh
            </button>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="panel p-5">
              <div className="eyebrow">system</div>
              <div className="mt-5 space-y-5">
                <div><div className="flex justify-between font-mono text-sm"><span>CPU</span><span>{formatPercent(runtimeStatus?.system?.cpu_percent)}</span></div><Meter value={runtimeStatus?.system?.cpu_percent} /></div>
                <div><div className="flex justify-between font-mono text-sm"><span>Memory</span><span>{formatMb(runtimeStatus?.system?.memory_used_mb)}</span></div><Meter value={runtimeStatus?.system?.memory_percent} /></div>
                <div><div className="flex justify-between font-mono text-sm"><span>Disk</span><span>{runtimeStatus?.system?.disk_used_gb?.toFixed(2) ?? "N/A"} GB</span></div><Meter value={runtimeStatus?.system?.disk_percent} /></div>
              </div>
            </div>
            <div className="panel p-5">
              <div className="eyebrow">project</div>
              <div className="mt-5 space-y-5">
                <div><div className="flex justify-between font-mono text-sm"><span>CPU</span><span>{formatPercent(runtimeStatus?.project?.cpu_percent)}</span></div><Meter value={runtimeStatus?.project?.cpu_percent} /></div>
                <div><div className="flex justify-between font-mono text-sm"><span>Memory</span><span>{formatMb(runtimeStatus?.project?.memory_used_mb)}</span></div><Meter value={runtimeStatus?.project?.memory_percent} /></div>
                <div><div className="flex justify-between font-mono text-sm"><span>Disk</span><span>{runtimeStatus?.project?.disk_used_gb?.toFixed(2) ?? "N/A"} GB</span></div><Meter value={runtimeStatus?.project?.disk_percent} /></div>
              </div>
            </div>
          </div>
          <div className="panel overflow-x-auto p-5">
            <div className="eyebrow">history</div>
            {resourceHistory.length === 0 ? (
              <div className="py-8 font-mono text-sm text-[var(--muted)]">No snapshots recorded.</div>
            ) : (
              <table className="mt-4 min-w-full text-left font-mono text-sm">
                <thead className="text-[var(--muted)]">
                  <tr><th className="py-2 pr-5">Time</th><th className="py-2 pr-5">CPU</th><th className="py-2 pr-5">Memory</th><th className="py-2 pr-5">Disk</th><th className="py-2 pr-5">Containers</th><th className="py-2">Apps</th></tr>
                </thead>
                <tbody>
                  {resourceHistory.map((snapshot) => (
                    <tr key={snapshot.id} className="border-t border-[rgba(24,26,31,0.12)]">
                      <td className="py-2 pr-5">{new Date(snapshot.timestamp).toLocaleTimeString()}</td>
                      <td className="py-2 pr-5">{formatPercent(snapshot.cpu_percent)}</td>
                      <td className="py-2 pr-5">{formatMb(snapshot.memory_used_mb)}</td>
                      <td className="py-2 pr-5">{snapshot.disk_used_gb?.toFixed(2) ?? "N/A"} GB</td>
                      <td className="py-2 pr-5">{snapshot.containers?.length || 0}</td>
                      <td className="py-2">{snapshot.apps?.length || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {activeTab === "diagnostics" && (
        <section className="space-y-5 py-6">
          <div className="flex flex-wrap gap-2">
            <button onClick={handleDoctor} disabled={doctorLoading} className="command-button">
              {doctorLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <CheckIcon />}
              Doctor
            </button>
            <button onClick={handleBuildLogs} disabled={buildLogsLoading} className="ghost-button">
              {buildLogsLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <TerminalIcon />}
              Build History
            </button>
          </div>
          {doctorReport && (
            <div className="panel p-5">
              <div className="flex flex-wrap items-center gap-3">
                <div className="eyebrow">doctor report</div>
                <span className="status-pill">
                  <span className={`status-dot ${doctorReport.all_ok ? "status-live" : "status-dead"}`} />
                  {doctorReport.all_ok ? "pass" : "issues"}
                </span>
              </div>
              <div className="mt-5 divide-y divide-[rgba(24,26,31,0.12)]">
                {doctorReport.checks.map((check, index) => (
                  <div key={`${check.label}-${index}`} className="grid gap-3 py-3 lg:grid-cols-[5rem_1fr_1fr]">
                    <span className={`font-mono text-sm font-black ${check.ok ? "text-[var(--green)]" : "text-[var(--coral)]"}`}>{check.ok ? "OK" : check.severity.toUpperCase()}</span>
                    <span className="font-bold">{check.label}</span>
                    <span className="font-mono text-sm text-[var(--muted)]">{check.detail || check.suggestion}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {buildLogsHistory.length > 0 && (
            <div className="space-y-4">
              {buildLogsHistory.map((entry) => (
                <div key={entry.id} className="panel p-5">
                  <div className="flex flex-wrap justify-between gap-3">
                    <div className="font-black">{entry.image}</div>
                    <div className="font-mono text-sm text-[var(--muted)]">{entry.status} | {entry.built_at}</div>
                  </div>
                  {entry.logs && <div className="mt-4"><LogViewer logs={entry.logs.slice(0, 3000)} /></div>}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {activeTab === "logs" && (
        <section className="py-6">
          <div className="mb-3 flex justify-end">
            <button onClick={fetchLogs} disabled={logsLoading} className="ghost-button">
              <RefreshIcon className={logsLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              Refresh
            </button>
          </div>
          <LogViewer logs={logs} loading={logsLoading} />
        </section>
      )}
    </div>
  );
}
