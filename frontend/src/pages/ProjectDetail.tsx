import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addProjectDependency,
  appLogs,
  AppStatus,
  buildProject,
  collectResourceSnapshot,
  CodeGraph,
  composeDown,
  composeLogs,
  composeUp,
  getProject,
  getProjectGraph,
  getResourceHistory,
  gitBranches,
  gitCommit,
  GitBranches,
  GitCommit,
  gitFetch,
  gitHistory,
  gitInit,
  gitPublish,
  gitPull,
  gitPush,
  gitStatus,
  GitStatus,
  gitSwitchBranch,
  indexProjectGraph,
  inspectProjectGraphNode,
  projectBuildLogs,
  projectDoctor,
  projectEnvironment,
  projectLogs,
  projectStatus,
  ProjectEnvironment,
  removeProjectEnvironmentVariable,
  searchProjectGraph,
  setProjectEnvironmentVariable,
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
  DownloadIcon,
  ExternalIcon,
  GitBranchIcon,
  GraphIcon,
  HammerIcon,
  PlayIcon,
  PlusIcon,
  RefreshIcon,
  StopIcon,
  TerminalIcon,
  UploadIcon,
} from "../components/icons";

type Action = "idle" | "building" | "starting" | "stopping";
type Tab = "overview" | "graph" | "environment" | "git" | "apps" | "resources" | "diagnostics" | "logs";

const tabs: Tab[] = ["overview", "graph", "environment", "git", "apps", "resources", "diagnostics", "logs"];

function formatError(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}

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

function TrendChart({
  label,
  values,
  unit,
  color,
}: {
  label: string;
  values: Array<{ timestamp: string; value: number | null }>;
  unit: string;
  color: string;
}) {
  const valid = values.filter((item) => typeof item.value === "number") as Array<{ timestamp: string; value: number }>;
  const width = 320;
  const height = 96;
  const padX = 12;
  const padY = 10;

  if (!valid.length) {
    return (
      <div className="panel p-4">
        <div className="eyebrow">{label}</div>
        <div className="mt-4 font-mono text-sm text-[var(--muted)]">No history yet.</div>
      </div>
    );
  }

  const max = Math.max(...valid.map((item) => item.value), 1);
  const min = Math.min(...valid.map((item) => item.value), 0);
  const range = Math.max(max - min, 1);
  const gradientId = `trend-${label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
  const points = valid.map((item, index) => {
    const x = padX + (index / Math.max(valid.length - 1, 1)) * (width - padX * 2);
    const y = height - padY - ((item.value - min) / range) * (height - padY * 2);
    return `${x},${y}`;
  });
  const latest = valid[valid.length - 1];
  const latestValue = latest.value.toFixed(latest.value >= 100 ? 0 : 1);

  return (
    <div className="panel p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">{label}</div>
          <div className="mt-2 font-mono text-lg font-black">
            {latestValue} {unit}
          </div>
        </div>
        <div className="font-mono text-xs text-[var(--muted)]">
          min {min.toFixed(1)} | max {max.toFixed(1)}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 h-24 w-full">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polygon fill={`url(#${gradientId})`} stroke="none" points={`0,${height} ${points.join(" ")} ${width},${height}`} />
        <polyline fill="none" stroke={color} strokeWidth="2.5" points={points.join(" ")} />
      </svg>
      <div className="mt-2 font-mono text-xs text-[var(--muted)]">latest {latest.timestamp}</div>
    </div>
  );
}

const graphPalette: Record<string, string> = {
  file: "var(--cyan)",
  function: "var(--green)",
  class: "var(--brass)",
  artifact: "var(--line-strong)",
  external: "var(--coral)",
};

function CodeGraphCanvas({
  graph,
  selectedId,
  onSelect,
}: {
  graph: CodeGraph;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const visibleNodes = graph.nodes.slice(0, 120);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = graph.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)).slice(0, 260);
  const width = 920;
  const height = 460;
  const centerX = width / 2;
  const centerY = height / 2;
  const positions = new Map<string, { x: number; y: number }>();
  const degree = new Map<string, number>();
  visibleEdges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  });

  function nodeLane(node: { kind: string }): number {
    if (node.kind === "file") return 0;
    if (node.kind === "class" || node.kind === "function") return 1;
    if (node.kind === "external") return 3;
    return 2;
  }

  visibleNodes.forEach((node, index) => {
    const relatedToSelected = selectedId
      ? visibleEdges.some((edge) => (edge.source === selectedId && edge.target === node.id) || (edge.target === selectedId && edge.source === node.id))
      : false;
    const nodeDegree = degree.get(node.id) || 0;
    const lane = nodeLane(node);
    const laneNodes = visibleNodes.filter((item) => nodeLane(item) === lane);
    const laneIndex = laneNodes.findIndex((item) => item.id === node.id);
    const y = 80 + lane * 100;
    const x = 80 + ((laneIndex + 1) / (laneNodes.length + 1)) * (width - 160);
    const pull = relatedToSelected ? 0.38 : selectedId === node.id ? 0.55 : Math.min(nodeDegree, 8) * 0.012;
    positions.set(node.id, {
      x: x + (centerX - x) * pull + Math.sin(index * 1.7) * 10,
      y: y + (centerY - y) * pull + Math.cos(index * 1.3) * 8,
    });
  });

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-[24rem] w-full">
      <defs>
        <pattern id="graph-grid" width="28" height="28" patternUnits="userSpaceOnUse">
          <path d="M 28 0 L 0 0 0 28" fill="none" stroke="rgba(24,26,31,0.08)" strokeWidth="1" />
        </pattern>
      </defs>
      <rect x="0" y="0" width={width} height={height} fill="rgba(255,252,245,0.45)" />
      <rect x="0" y="0" width={width} height={height} fill="url(#graph-grid)" />
      {visibleEdges.map((edge, index) => {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) return null;
        const active = edge.source === selectedId || edge.target === selectedId;
        return (
          <line
            key={`${edge.source}-${edge.target}-${edge.kind}-${index}`}
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            stroke={active ? "rgba(24,26,31,0.6)" : edge.kind === "calls" ? "rgba(39,122,77,0.38)" : "rgba(24,26,31,0.16)"}
            strokeWidth={active ? 2.4 : edge.kind === "calls" ? 1.6 : 1}
          />
        );
      })}
      {visibleNodes.map((node) => {
        const position = positions.get(node.id);
        if (!position) return null;
        const active = selectedId === node.id;
        const related = selectedId ? visibleEdges.some((edge) => (edge.source === selectedId && edge.target === node.id) || (edge.target === selectedId && edge.source === node.id)) : false;
        const color = graphPalette[node.kind] || "var(--ink)";
        return (
          <g
            key={node.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(node.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") onSelect(node.id);
            }}
            className="cursor-pointer"
          >
            <circle
              cx={position.x}
              cy={position.y}
              r={active ? 11 : related ? 8 : node.kind === "file" ? 7 : 5}
              fill={color}
              opacity={selectedId && !active && !related ? 0.38 : 1}
              stroke={active ? "var(--ink)" : related ? "rgba(24,26,31,0.55)" : "rgba(255,252,245,0.9)"}
              strokeWidth={active ? 4 : 2}
            />
            {(active || related || node.kind === "file") && (
              <text x={position.x + 10} y={position.y - 8} className="fill-[var(--ink)] font-mono text-[10px] font-bold">
                {node.label.length > 28 ? `${node.label.slice(0, 25)}...` : node.label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
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
  const [gitState, setGitState] = useState<GitStatus | null>(null);
  const [gitBranchState, setGitBranchState] = useState<GitBranches | null>(null);
  const [gitHistoryRows, setGitHistoryRows] = useState<GitCommit[]>([]);
  const [gitLoading, setGitLoading] = useState<string | null>(null);
  const [gitMessage, setGitMessage] = useState("Save project changes");
  const [gitRemoteUrl, setGitRemoteUrl] = useState("");
  const [gitBranchName, setGitBranchName] = useState("");
  const [gitRemoteName, setGitRemoteName] = useState("origin");
  const [gitSetUpstream, setGitSetUpstream] = useState(true);
  const [gitOutput, setGitOutput] = useState("");
  const [environment, setEnvironment] = useState<ProjectEnvironment | null>(null);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [dependencyInput, setDependencyInput] = useState("");
  const [envNameInput, setEnvNameInput] = useState("");
  const [envValueInput, setEnvValueInput] = useState("");
  const [codeGraph, setCodeGraph] = useState<CodeGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [graphFilter, setGraphFilter] = useState("");
  const [graphKindFilter, setGraphKindFilter] = useState("");
  const [graphDepth, setGraphDepth] = useState(1);
  const [graphMode, setGraphMode] = useState<"full" | "search" | "focus">("full");

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    try {
      setDetail(await getProject(id));
    } catch (e: unknown) {
      setError(formatError(e, "Failed to load project"));
    }
  }, [id]);

  const fetchRuntimeStatus = useCallback(async () => {
    if (!id) return;
    try {
      const status = await projectStatus(id);
      setRuntimeStatus(status);
      setGitState(status.git);
      setAppStatuses(Object.fromEntries(status.apps.map((app) => [app.app_id, app])));
    } catch {
      /* keep previous status visible */
    }
  }, [id]);

  const fetchGitControl = useCallback(async () => {
    if (!id) return;
    try {
      const status = await gitStatus(id);
      setGitState(status);
      if (!status.is_repo) {
        setGitBranchState(null);
        setGitHistoryRows([]);
        return;
      }
      const [branches, history] = await Promise.all([gitBranches(id), gitHistory(id, 8)]);
      setGitBranchState(branches);
      setGitHistoryRows(history);
    } catch (e: unknown) {
      setError(formatError(e, "Failed to load Git state"));
    }
  }, [id]);

  const fetchEnvironment = useCallback(async () => {
    if (!id) return;
    setEnvironmentLoading(true);
    try {
      setEnvironment(await projectEnvironment(id));
    } catch (e: unknown) {
      setError(formatError(e, "Failed to load environment"));
    } finally {
      setEnvironmentLoading(false);
    }
  }, [id]);

  const fetchCodeGraph = useCallback(async (reindex = false) => {
    if (!id) return;
    setGraphLoading(true);
    setError(null);
    try {
      const graph = reindex ? await indexProjectGraph(id) : await getProjectGraph(id);
      setCodeGraph(graph);
      setGraphMode("full");
      setSelectedGraphNodeId((current) => current && graph.nodes.some((node) => node.id === current) ? current : graph.summary.hotspots[0]?.id ?? graph.nodes[0]?.id ?? null);
    } catch (e: unknown) {
      setError(formatError(e, "Failed to analyze code graph"));
    } finally {
      setGraphLoading(false);
    }
  }, [id]);

  const searchCodeGraph = useCallback(async () => {
    if (!id) return;
    setGraphLoading(true);
    setError(null);
    try {
      const graph = await searchProjectGraph(id, graphFilter, graphKindFilter || undefined, 40);
      setCodeGraph(graph);
      setGraphMode("search");
      setSelectedGraphNodeId(graph.summary.hotspots[0]?.id ?? graph.nodes[0]?.id ?? null);
    } catch (e: unknown) {
      setError(formatError(e, "Failed to search code graph"));
    } finally {
      setGraphLoading(false);
    }
  }, [graphFilter, graphKindFilter, id]);

  const inspectGraphNode = useCallback(async (nodeId: string) => {
    if (!id) return;
    setGraphLoading(true);
    setError(null);
    try {
      const inspection = await inspectProjectGraphNode(id, nodeId, graphDepth);
      setCodeGraph(inspection.graph);
      setGraphMode("focus");
      setSelectedGraphNodeId(inspection.node.id);
    } catch (e: unknown) {
      setError(formatError(e, "Failed to inspect graph node"));
    } finally {
      setGraphLoading(false);
    }
  }, [graphDepth, id]);

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
      setError(formatError(e, "Failed to load resource history"));
    } finally {
      setResourceLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
    fetchRuntimeStatus();
    fetchGitControl();
  }, [fetchDetail, fetchGitControl, fetchRuntimeStatus]);

  useEffect(() => {
    if (runtimeStatus?.container_running || detail?.container_running) {
      const interval = setInterval(fetchRuntimeStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [detail?.container_running, fetchRuntimeStatus, runtimeStatus?.container_running]);

  useEffect(() => {
    if (activeTab === "resources" && resourceHistory.length === 0) fetchResourceHistory();
    if (activeTab === "logs" && !logs) fetchLogs();
    if (activeTab === "git") fetchGitControl();
    if (activeTab === "environment" && !environment) fetchEnvironment();
    if (activeTab === "graph" && !codeGraph) fetchCodeGraph();
  }, [activeTab, codeGraph, environment, fetchCodeGraph, fetchEnvironment, fetchGitControl, fetchLogs, fetchResourceHistory, logs, resourceHistory.length]);

  const running = runtimeStatus?.container_running ?? detail?.container_running ?? false;
  const apps = useMemo(() => detail?.config.apps ?? [], [detail]);
  const currentGit = gitState ?? runtimeStatus?.git ?? null;
  const currentBranch = gitBranchState?.current || currentGit?.branch || "";
  const selectedGraphNode = codeGraph?.nodes.find((node) => node.id === selectedGraphNodeId) ?? null;
  const graphKinds = useMemo(() => Array.from(new Set(codeGraph?.nodes.map((node) => node.kind) ?? [])).sort(), [codeGraph]);
  const filteredGraphNodes = useMemo(() => {
    const query = graphFilter.trim().toLowerCase();
    if (!codeGraph) return [];
    return codeGraph.nodes
      .filter((node) => !query || node.label.toLowerCase().includes(query) || node.kind.toLowerCase().includes(query) || node.file_path.toLowerCase().includes(query))
      .slice(0, 80);
  }, [codeGraph, graphFilter]);
  const selectedGraphEdges = useMemo(() => {
    if (!codeGraph || !selectedGraphNodeId) return [];
    return codeGraph.edges.filter((edge) => edge.source === selectedGraphNodeId || edge.target === selectedGraphNodeId).slice(0, 24);
  }, [codeGraph, selectedGraphNodeId]);
  const latestResourceSnapshot = resourceHistory[0] ?? null;
  const resourceTrendPoints = useMemo(() => {
    return [...resourceHistory]
      .reverse()
      .map((snapshot) => ({
        timestamp: new Date(snapshot.timestamp).toLocaleTimeString(),
        cpu: snapshot.cpu_percent,
        memory: snapshot.memory_percent,
        disk: snapshot.disk_percent,
      }));
  }, [resourceHistory]);
  const latestContainers = useMemo(() => {
    return [...(latestResourceSnapshot?.containers ?? [])]
      .sort((a, b) => (b.cpu_percent ?? -1) - (a.cpu_percent ?? -1))
      .slice(0, 5);
  }, [latestResourceSnapshot]);
  const latestApps = useMemo(() => {
    return [...(latestResourceSnapshot?.apps ?? [])]
      .sort((a, b) => (b.cpu_percent ?? -1) - (a.cpu_percent ?? -1))
      .slice(0, 5);
  }, [latestResourceSnapshot]);

  async function runGitAction(label: string, actionFn: () => Promise<{ status: string; output?: string; commit?: string }>) {
    setGitLoading(label);
    setError(null);
    try {
      const result = await actionFn();
      const lines = [
        `${label}: ${result.status}`,
        result.commit ? `commit ${result.commit}` : "",
        result.output || "",
      ].filter(Boolean);
      setGitOutput(lines.join("\n"));
      await fetchGitControl();
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(formatError(e, `${label} failed`));
    } finally {
      setGitLoading(null);
    }
  }

  async function handleBuild() {
    if (!id) return;
    setAction("building");
    setError(null);
    try {
      await buildProject(id);
      await fetchDetail();
      await fetchRuntimeStatus();
    } catch (e: unknown) {
      setError(formatError(e, "Build failed"));
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
      setError(formatError(e, "Start failed"));
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
      setError(formatError(e, "Stop failed"));
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
      setError(formatError(e, `Failed to start ${appId}`));
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
      setError(formatError(e, `Failed to stop ${appId}`));
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
      setError(formatError(e, "Failed to start Compose services"));
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
      setError(formatError(e, "Failed to stop Compose services"));
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
      setError(formatError(e, "Failed to load Compose logs"));
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
      setError(formatError(e, "Doctor check failed"));
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
      setError(formatError(e, "Failed to load build history"));
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
      setError(formatError(e, "Failed to collect resources"));
    } finally {
      setResourceLoading(false);
    }
  }

  async function handleAddDependency() {
    if (!id) return;
    const dependency = dependencyInput.trim();
    if (!dependency) {
      setError("Dependency is required");
      return;
    }
    setEnvironmentLoading(true);
    setError(null);
    try {
      setEnvironment(await addProjectDependency(id, dependency));
      setDependencyInput("");
    } catch (e: unknown) {
      setError(formatError(e, "Failed to add dependency"));
    } finally {
      setEnvironmentLoading(false);
    }
  }

  async function handleSetEnvironmentVariable() {
    if (!id) return;
    const name = envNameInput.trim();
    if (!name) {
      setError("Environment variable name is required");
      return;
    }
    setEnvironmentLoading(true);
    setError(null);
    try {
      setEnvironment(await setProjectEnvironmentVariable(id, name, envValueInput));
      setEnvNameInput("");
      setEnvValueInput("");
      await fetchDetail();
    } catch (e: unknown) {
      setError(formatError(e, "Failed to set environment variable"));
    } finally {
      setEnvironmentLoading(false);
    }
  }

  async function handleRemoveEnvironmentVariable(name: string) {
    if (!id) return;
    setEnvironmentLoading(true);
    setError(null);
    try {
      setEnvironment(await removeProjectEnvironmentVariable(id, name));
      await fetchDetail();
    } catch (e: unknown) {
      setError(formatError(e, "Failed to remove environment variable"));
    } finally {
      setEnvironmentLoading(false);
    }
  }

  async function handleGitInit() {
    if (!id) return;
    await runGitAction("Initialize repository", () => gitInit(id));
  }

  async function handleGitRefresh() {
    setGitLoading("Refresh");
    try {
      await fetchGitControl();
    } finally {
      setGitLoading(null);
    }
  }

  async function handleGitCommit() {
    if (!id) return;
    const message = gitMessage.trim();
    if (!message) {
      setError("Commit message is required");
      return;
    }
    await runGitAction("Commit", () => gitCommit(id, message, true));
  }

  async function handleGitSwitchBranch(create: boolean, selectedBranch?: string) {
    if (!id) return;
    const branch = (selectedBranch ?? gitBranchName).trim();
    if (!branch) {
      setError("Branch name is required");
      return;
    }
    await runGitAction(create ? "Create branch" : "Switch branch", () => gitSwitchBranch(id, branch, create));
  }

  async function handleGitFetch() {
    if (!id) return;
    await runGitAction("Fetch", () => gitFetch(id, gitRemoteName.trim() || "origin"));
  }

  async function handleGitPull() {
    if (!id) return;
    await runGitAction("Pull", () => gitPull(id, gitRemoteName.trim() || "origin", currentBranch || undefined));
  }

  async function handleGitPush() {
    if (!id) return;
    await runGitAction("Push", () => gitPush(id, gitRemoteName.trim() || "origin", currentBranch || undefined, gitSetUpstream));
  }

  async function handleGitPublish() {
    if (!id) return;
    const remoteUrl = gitRemoteUrl.trim();
    if (!remoteUrl) {
      setError("Remote URL is required");
      return;
    }
    await runGitAction("Publish", () => gitPublish(id, remoteUrl, gitRemoteName.trim() || "origin", currentBranch || undefined));
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
              <div>{currentGit?.is_repo ? currentGit.branch || "detached HEAD" : "Not a Git repo"}</div>
              <div className="truncate text-[var(--muted)]">{currentGit?.remote || "No remote"}</div>
              <div className={currentGit?.dirty_files ? "text-[var(--brass)]" : "text-[var(--muted)]"}>
                {currentGit?.dirty_files ?? 0} dirty files
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
              <div>{currentGit?.lfs_available ? "Git LFS available" : "Git LFS optional"}</div>
            </div>
          </div>
        </section>
      )}

      {activeTab === "graph" && (
        <section className="space-y-5 py-6">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="panel overflow-hidden">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgba(24,26,31,0.14)] p-5">
                <div>
                  <div className="eyebrow">native code graph</div>
                  <h2 className="mt-3 text-2xl font-black">Code analysis map</h2>
                  <div className="mt-2 font-mono text-sm text-[var(--muted)]">
                    {codeGraph ? `${codeGraph.summary.node_count} nodes | ${codeGraph.summary.edge_count} edges` : "No graph loaded"}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => fetchCodeGraph(false)} disabled={graphLoading} className="ghost-button">
                    <RefreshIcon className={graphLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                    Load
                  </button>
                  <button onClick={() => fetchCodeGraph(true)} disabled={graphLoading} className="command-button">
                    {graphLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <GraphIcon />}
                    Analyze
                  </button>
                </div>
              </div>
              {codeGraph ? (
                <CodeGraphCanvas graph={codeGraph} selectedId={selectedGraphNodeId} onSelect={(nodeId) => inspectGraphNode(nodeId)} />
              ) : (
                <div className="grid h-[24rem] place-items-center p-5 font-mono text-sm text-[var(--muted)]">
                  Analyze the project to build a local code graph.
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="panel p-5">
                <div className="eyebrow">analysis</div>
                <div className="mt-2 font-mono text-xs text-[var(--muted)]">{graphMode} graph</div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="metric">
                    <div className="eyebrow">nodes</div>
                    <div className="mt-2 font-mono text-xl font-black">{codeGraph?.summary.node_count ?? 0}</div>
                  </div>
                  <div className="metric">
                    <div className="eyebrow">edges</div>
                    <div className="mt-2 font-mono text-xl font-black">{codeGraph?.summary.edge_count ?? 0}</div>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {codeGraph ? Object.entries(codeGraph.summary.components).map(([kind, count]) => (
                    <span key={kind} className="status-pill">
                      <span className="status-dot" style={{ background: graphPalette[kind] || "var(--muted)" }} />
                      {kind} {count}
                    </span>
                  )) : null}
                </div>
                <div className="mt-5 grid grid-cols-4 gap-2">
                  {[0, 1, 2, 3].map((depth) => (
                    <button
                      key={depth}
                      onClick={() => setGraphDepth(depth)}
                      className={`ghost-button ${graphDepth === depth ? "border-[var(--ink)] bg-[rgba(24,26,31,0.08)]" : ""}`}
                    >
                      {depth}
                    </button>
                  ))}
                </div>
              </div>

              <div className="panel p-5">
                <div className="eyebrow">selected node</div>
                {selectedGraphNode ? (
                  <div className="mt-4 space-y-3">
                    <div className="font-black">{selectedGraphNode.label}</div>
                    <div className="status-pill">{selectedGraphNode.kind}</div>
                    <div className="break-all font-mono text-xs text-[var(--muted)]">{selectedGraphNode.file_path || selectedGraphNode.id}</div>
                    {typeof selectedGraphNode.metadata.line === "number" && (
                      <div className="font-mono text-sm text-[var(--muted)]">line {selectedGraphNode.metadata.line}</div>
                    )}
                    <button onClick={() => inspectGraphNode(selectedGraphNode.id)} disabled={graphLoading} className="command-button">
                      {graphLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <GraphIcon />}
                      Expand
                    </button>
                  </div>
                ) : (
                  <div className="mt-4 font-mono text-sm text-[var(--muted)]">Select a node in the graph.</div>
                )}
              </div>
            </div>
          </div>

          {codeGraph && (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
              <div className="panel p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="eyebrow">nodes</div>
                    <div className="mt-2 font-mono text-sm text-[var(--muted)]">Filter files, symbols, artifacts, and external imports.</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <select value={graphKindFilter} onChange={(e) => setGraphKindFilter(e.target.value)} className="field max-w-[10rem]">
                      <option value="">all kinds</option>
                      {graphKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
                    </select>
                    <input
                      value={graphFilter}
                      onChange={(e) => setGraphFilter(e.target.value)}
                      className="field max-w-xs"
                      placeholder="search symbols/files"
                    />
                    <button onClick={searchCodeGraph} disabled={graphLoading} className="command-button">
                      {graphLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <GraphIcon />}
                      Search
                    </button>
                  </div>
                </div>
                <div className="mt-4 max-h-[28rem] overflow-auto divide-y divide-[rgba(24,26,31,0.12)]">
                  {filteredGraphNodes.map((node) => (
                    <button
                      key={node.id}
                      onClick={() => inspectGraphNode(node.id)}
                      className={`grid w-full gap-2 py-3 text-left sm:grid-cols-[7rem_minmax(0,1fr)_5rem] ${selectedGraphNodeId === node.id ? "text-[var(--cyan)]" : ""}`}
                    >
                      <span className="status-pill">
                        <span className="status-dot" style={{ background: graphPalette[node.kind] || "var(--muted)" }} />
                        {node.kind}
                      </span>
                      <span className="min-w-0 truncate font-mono text-sm font-bold">{node.label}</span>
                      <span className="font-mono text-xs text-[var(--muted)]">{String(node.metadata.language || "")}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <div className="panel p-5">
                  <div className="eyebrow">hotspots</div>
                  <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                    {codeGraph.summary.hotspots.map((node) => (
                      <button key={node.id} onClick={() => inspectGraphNode(node.id)} className="grid w-full grid-cols-[1fr_auto] gap-3 py-3 text-left">
                        <span className="min-w-0 truncate font-bold">{node.label}</span>
                        <span className="font-mono text-xs text-[var(--muted)]">{node.degree}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="panel p-5">
                  <div className="eyebrow">connections</div>
                  <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                    {selectedGraphEdges.length ? selectedGraphEdges.map((edge, index) => {
                      const otherId = edge.source === selectedGraphNodeId ? edge.target : edge.source;
                      const other = codeGraph.nodes.find((node) => node.id === otherId);
                      return (
                        <button key={`${edge.source}-${edge.target}-${index}`} onClick={() => inspectGraphNode(otherId)} className="w-full py-3 text-left">
                          <div className="font-mono text-xs text-[var(--muted)]">{edge.kind}</div>
                          <div className="mt-1 truncate font-bold">{other?.label || otherId}</div>
                        </button>
                      );
                    }) : (
                      <div className="py-6 font-mono text-sm text-[var(--muted)]">No direct connections.</div>
                    )}
                  </div>
                </div>

                {codeGraph.summary.risks.length ? (
                  <div className="panel p-5">
                    <div className="eyebrow">signals</div>
                    <div className="mt-4 space-y-2">
                      {codeGraph.summary.risks.map((risk) => (
                        <div key={risk} className="font-mono text-sm text-[var(--brass)]">{risk}</div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </section>
      )}

      {activeTab === "environment" && (
        <section className="space-y-5 py-6">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="panel p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="eyebrow">container environment</div>
                  <h2 className="mt-3 text-2xl font-black">Runtime inputs</h2>
                  <p className="mt-2 font-mono text-sm text-[var(--muted)]">{detail.path}</p>
                </div>
                <button onClick={fetchEnvironment} disabled={environmentLoading} className="ghost-button">
                  <RefreshIcon className={environmentLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                  Refresh
                </button>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-4">
                <div className="metric">
                  <div className="eyebrow">image</div>
                  <div className="mt-2 truncate font-mono text-lg font-black">{environment?.runtime.image || detail.config.runtime.image}</div>
                </div>
                <div className="metric">
                  <div className="eyebrow">runtime</div>
                  <div className="mt-2 font-mono text-lg font-black">{environment?.runtime.type || detail.config.runtime.type}</div>
                </div>
                <div className="metric">
                  <div className="eyebrow">dockerfile</div>
                  <div className="mt-2 truncate font-mono text-lg font-black">{environment?.runtime.dockerfile || detail.config.runtime.dockerfile}</div>
                </div>
                <div className={`metric ${environment?.runtime.gpu || detail.config.runtime.gpu ? "metric-active" : ""}`}>
                  <div className="eyebrow">gpu</div>
                  <div className="mt-2 font-mono text-lg font-black">{environment?.runtime.gpu || detail.config.runtime.gpu ? "enabled" : "disabled"}</div>
                </div>
              </div>
            </div>

            <div className="panel p-5">
              <div className="eyebrow">dependency file</div>
              <div className="mt-4 font-mono text-xl font-black">{environment?.dependency_file || "requirements.txt"}</div>
              <div className="mt-2 font-mono text-sm text-[var(--muted)]">
                {environment?.dependency_file_exists ? "present in project root" : "will be created on first add"}
              </div>
              <div className="mt-5 flex flex-col gap-3">
                <input
                  value={dependencyInput}
                  onChange={(e) => setDependencyInput(e.target.value)}
                  className="field"
                  placeholder="numpy>=2.0"
                />
                <button onClick={handleAddDependency} disabled={environmentLoading} className="command-button">
                  {environmentLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <PlusIcon />}
                  Add dependency
                </button>
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="panel p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="eyebrow">dependencies</div>
                  <div className="mt-2 font-mono text-sm text-[var(--muted)]">{environment?.dependencies.length ?? 0} packages declared</div>
                </div>
              </div>
              <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                {environment?.dependencies.length ? environment.dependencies.map((dependency) => (
                  <div key={dependency} className="flex items-center justify-between gap-3 py-3">
                    <span className="min-w-0 truncate font-mono text-sm font-bold">{dependency}</span>
                    <span className="status-pill">python</span>
                  </div>
                )) : (
                  <div className="py-8 font-mono text-sm text-[var(--muted)]">No dependencies declared yet.</div>
                )}
              </div>
            </div>

            <div className="panel p-5">
              <div className="eyebrow">environment variables</div>
              <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)_auto]">
                <input
                  value={envNameInput}
                  onChange={(e) => setEnvNameInput(e.target.value)}
                  className="field"
                  placeholder="API_URL"
                />
                <input
                  value={envValueInput}
                  onChange={(e) => setEnvValueInput(e.target.value)}
                  className="field"
                  placeholder="https://example.test"
                />
                <button onClick={handleSetEnvironmentVariable} disabled={environmentLoading} className="command-button">
                  {environmentLoading ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <CheckIcon />}
                  Set
                </button>
              </div>
              <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                {environment && Object.keys(environment.environment).length ? Object.entries(environment.environment).map(([name, value]) => (
                  <div key={name} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)_auto]">
                    <span className="min-w-0 truncate font-mono text-sm font-black">{name}</span>
                    <span className="min-w-0 truncate font-mono text-sm text-[var(--muted)]">{value}</span>
                    <button onClick={() => handleRemoveEnvironmentVariable(name)} disabled={environmentLoading} className="danger-button">
                      Remove
                    </button>
                  </div>
                )) : (
                  <div className="py-8 font-mono text-sm text-[var(--muted)]">No environment variables configured.</div>
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === "git" && (
        <section className="space-y-5 py-6">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="panel p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="eyebrow">repository</div>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <span className="status-pill">
                      <span className={`status-dot ${currentGit?.is_repo ? "status-live" : "status-dead"}`} />
                      {currentGit?.is_repo ? "tracked" : "not initialized"}
                    </span>
                    <span className="font-mono text-sm text-[var(--muted)]">
                      {currentGit?.is_repo ? currentBranch || "detached HEAD" : detail.path}
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={handleGitRefresh} disabled={Boolean(gitLoading)} className="ghost-button">
                    <RefreshIcon className={gitLoading === "Refresh" ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
                    Refresh
                  </button>
                  {!currentGit?.is_repo && (
                    <button onClick={handleGitInit} disabled={Boolean(gitLoading)} className="command-button">
                      {gitLoading === "Initialize repository" ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <GitBranchIcon />}
                      Initialize
                    </button>
                  )}
                </div>
              </div>

              {currentGit?.is_repo && (
                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  <div className="metric">
                    <div className="eyebrow">branch</div>
                    <div className="mt-2 truncate font-mono text-lg font-black">{currentBranch || "detached"}</div>
                  </div>
                  <div className={`metric ${currentGit.dirty_files ? "metric-warn" : "metric-active"}`}>
                    <div className="eyebrow">worktree</div>
                    <div className="mt-2 font-mono text-lg font-black">{currentGit.dirty_files} dirty</div>
                  </div>
                  <div className="metric">
                    <div className="eyebrow">remote</div>
                    <div className="mt-2 truncate font-mono text-lg font-black">{currentGit.remote ? currentGit.remote.split(/\s+/)[0] : "none"}</div>
                  </div>
                </div>
              )}
            </div>

            <div className="panel p-5">
              <div className="eyebrow">remote control</div>
              <label className="mt-4 block">
                <span className="font-mono text-xs font-bold uppercase text-[var(--muted)]">remote</span>
                <input value={gitRemoteName} onChange={(e) => setGitRemoteName(e.target.value)} className="field mt-2" />
              </label>
              <label className="mt-3 flex items-center gap-2 font-mono text-sm text-[var(--muted)]">
                <input type="checkbox" checked={gitSetUpstream} onChange={(e) => setGitSetUpstream(e.target.checked)} />
                set upstream when pushing
              </label>
              <div className="mt-4 grid grid-cols-3 gap-2">
                <button onClick={handleGitFetch} disabled={!currentGit?.is_repo || Boolean(gitLoading)} className="ghost-button">
                  <DownloadIcon />
                  Fetch
                </button>
                <button onClick={handleGitPull} disabled={!currentGit?.is_repo || Boolean(gitLoading)} className="ghost-button">
                  <DownloadIcon />
                  Pull
                </button>
                <button onClick={handleGitPush} disabled={!currentGit?.is_repo || Boolean(gitLoading)} className="ghost-button">
                  <UploadIcon />
                  Push
                </button>
              </div>
            </div>
          </div>

          {currentGit?.is_repo && (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="panel p-5">
                <div className="eyebrow">commit</div>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <input
                    value={gitMessage}
                    onChange={(e) => setGitMessage(e.target.value)}
                    className="field min-w-0 flex-1"
                    placeholder="Commit message"
                  />
                  <button onClick={handleGitCommit} disabled={Boolean(gitLoading)} className="command-button">
                    {gitLoading === "Commit" ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <CheckIcon />}
                    Commit all
                  </button>
                </div>
              </div>

              <div className="panel p-5">
                <div className="eyebrow">branches</div>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <input
                    value={gitBranchName}
                    onChange={(e) => setGitBranchName(e.target.value)}
                    className="field min-w-0 flex-1"
                    placeholder="feature/data-cleanup"
                  />
                  <button onClick={() => handleGitSwitchBranch(false)} disabled={Boolean(gitLoading)} className="ghost-button">
                    <GitBranchIcon />
                    Switch
                  </button>
                  <button onClick={() => handleGitSwitchBranch(true)} disabled={Boolean(gitLoading)} className="command-button">
                    <GitBranchIcon />
                    Create
                  </button>
                </div>
                {gitBranchState?.branches.length ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {gitBranchState.branches.map((branch) => (
                      <button
                        key={branch.name}
                        onClick={() => {
                          setGitBranchName(branch.name);
                          if (!branch.current) handleGitSwitchBranch(false, branch.name);
                        }}
                        className={`status-pill ${branch.current ? "border-[var(--ink)] text-[var(--ink)]" : ""}`}
                        disabled={branch.current || Boolean(gitLoading)}
                      >
                        <span className={`status-dot ${branch.current ? "status-live" : ""}`} />
                        {branch.name}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="panel p-5">
                <div className="eyebrow">publish</div>
                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <input
                    value={gitRemoteUrl}
                    onChange={(e) => setGitRemoteUrl(e.target.value)}
                    className="field min-w-0 flex-1"
                    placeholder="git@github.com:org/repo.git"
                  />
                  <button onClick={handleGitPublish} disabled={Boolean(gitLoading)} className="command-button">
                    {gitLoading === "Publish" ? <RefreshIcon className="h-4 w-4 animate-spin" /> : <UploadIcon />}
                    Publish
                  </button>
                </div>
              </div>

              <div className="panel p-5">
                <div className="eyebrow">recent commits</div>
                <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                  {gitHistoryRows.length ? gitHistoryRows.map((commit) => (
                    <div key={commit.hash} className="grid gap-2 py-3 sm:grid-cols-[5rem_1fr_auto]">
                      <span className="font-mono text-sm font-black">{commit.hash}</span>
                      <span className="min-w-0 truncate font-bold">{commit.subject}</span>
                      <span className="font-mono text-xs text-[var(--muted)]">{commit.date}</span>
                    </div>
                  )) : (
                    <div className="py-6 font-mono text-sm text-[var(--muted)]">No commits yet.</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {gitOutput && (
            <div className="panel p-5">
              <div className="eyebrow">git output</div>
              <div className="mt-4">
                <LogViewer logs={gitOutput} />
              </div>
            </div>
          )}
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
              <RefreshIcon className={resourceLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              Refresh
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <TrendChart
              label="CPU trend"
              values={resourceTrendPoints.map((point) => ({ timestamp: point.timestamp, value: point.cpu }))}
              unit="%"
              color="var(--cyan)"
            />
            <TrendChart
              label="Memory trend"
              values={resourceTrendPoints.map((point) => ({ timestamp: point.timestamp, value: point.memory }))}
              unit="%"
              color="var(--green)"
            />
            <TrendChart
              label="Disk trend"
              values={resourceTrendPoints.map((point) => ({ timestamp: point.timestamp, value: point.disk }))}
              unit="%"
              color="var(--brass)"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-4">
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
            <div className="panel p-5">
              <div className="eyebrow">latest snapshot</div>
              <div className="mt-4 space-y-2 font-mono text-sm">
                <div>{latestResourceSnapshot ? new Date(latestResourceSnapshot.timestamp).toLocaleString() : "No snapshots recorded"}</div>
                <div>{latestResourceSnapshot?.containers?.length ?? 0} containers</div>
                <div>{latestResourceSnapshot?.apps?.length ?? 0} apps</div>
                <div>{latestResourceSnapshot?.compose_services?.length ?? 0} compose services</div>
              </div>
            </div>
            <div className="panel p-5">
              <div className="eyebrow">capture cadence</div>
              <div className="mt-4 space-y-2 font-mono text-sm text-[var(--muted)]">
                <div>{resourceHistory.length} snapshots loaded</div>
                <div>{resourceLoading ? "refreshing" : "idle"}</div>
                <div>{runtimeStatus?.container_running ? "runtime active" : "runtime stopped"}</div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
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

            <div className="space-y-4">
              <div className="panel p-5">
                <div className="eyebrow">containers</div>
                <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                  {latestContainers.length ? latestContainers.map((container) => (
                    <div key={container.id} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_8rem_8rem]">
                      <span className="min-w-0 truncate font-bold">{container.container_name}</span>
                      <span className="font-mono text-sm text-[var(--muted)]">CPU {formatPercent(container.cpu_percent)}</span>
                      <span className="font-mono text-sm text-[var(--muted)]">Mem {formatMb(container.memory_used_mb)}</span>
                    </div>
                  )) : (
                    <div className="py-6 font-mono text-sm text-[var(--muted)]">No container-level resource data.</div>
                  )}
                </div>
              </div>

              <div className="panel p-5">
                <div className="eyebrow">apps</div>
                <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                  {latestApps.length ? latestApps.map((app) => (
                    <div key={app.id} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_8rem_8rem]">
                      <span className="min-w-0 truncate font-bold">{app.app_name}</span>
                      <span className="font-mono text-sm text-[var(--muted)]">CPU {formatPercent(app.cpu_percent)}</span>
                      <span className="font-mono text-sm text-[var(--muted)]">Mem {formatMb(app.memory_used_mb)}</span>
                    </div>
                  )) : (
                    <div className="py-6 font-mono text-sm text-[var(--muted)]">No app-level resource data.</div>
                  )}
                </div>
              </div>

              <div className="panel p-5">
                <div className="eyebrow">compose services</div>
                <div className="mt-4 divide-y divide-[rgba(24,26,31,0.12)]">
                  {(latestResourceSnapshot?.compose_services ?? []).length ? latestResourceSnapshot!.compose_services.map((service) => (
                    <div key={service.id} className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_8rem_8rem]">
                      <span className="min-w-0 truncate font-bold">{service.service_name}</span>
                      <span className="font-mono text-sm text-[var(--muted)]">CPU {formatPercent(service.cpu_percent)}</span>
                      <span className="font-mono text-sm text-[var(--muted)]">{service.health_status || "unknown"}</span>
                    </div>
                  )) : (
                    <div className="py-6 font-mono text-sm text-[var(--muted)]">No Compose service metrics captured.</div>
                  )}
                </div>
              </div>
            </div>
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
