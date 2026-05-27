const API = "http://localhost:8000/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export interface ProjectRow {
  id: string;
  name: string;
  path: string;
  container_running: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends ProjectRow {
  config: {
    name: string;
    description: string | null;
    runtime: { type: string; dockerfile: string; image: string; gpu: boolean };
    apps: { name: string; id: string; command: string; port: number | null; url_path: string; kind: string }[];
  };
  container_running: boolean;
}

export interface ProjectStatus {
  name: string;
  project_id: string;
  container: string;
  container_running: boolean;
  docker: {
    available: boolean;
    binary_found: boolean;
    daemon_running: boolean;
    socket_accessible: boolean;
    version: string;
    error: string;
  };
  gpu_available: boolean;
  gpu_name: string;
  gpu_vram_mb: number;
  readiness: {
    ok: boolean;
    warnings: string[];
  };
  apps: AppStatus[];
  compose: ComposeStatus;
  build: { image: string; image_id: string | null; digest: string | null; built_at: string } | null;
  git: GitStatus;
  resources: {
    disk: { path: string; total_bytes: number; used_bytes: number; free_bytes: number; free_percent: number };
    gpu: { available: boolean; gpus: { name: string; utilization_percent: number; memory_used_mb: number; memory_total_mb: number }[] };
  };
  secrets: {
    configured: { name: string; location: string | null; required: boolean }[];
    present: { name: string; location: string | null; updated_at: string }[];
    missing: string[];
  };
  // Extended resource monitoring fields
  system?: {
    cpu_percent: number | null;
    memory_used_mb: number | null;
    memory_total_mb: number | null;
    memory_percent: number | null;
    disk_used_gb: number | null;
    disk_total_gb: number | null;
    disk_percent: number | null;
  };
  project?: {
    cpu_percent: number | null;
    memory_used_mb: number | null;
    memory_total_mb: number | null;
    memory_percent: number | null;
    disk_used_gb: number | null;
    disk_total_gb: number | null;
    disk_percent: number | null;
  };
}

export interface GitStatus {
  is_repo: boolean;
  branch: string;
  remote: string;
  dirty_files: number;
  lfs_available: boolean;
}

export interface GitCommit {
  hash: string;
  author: string;
  date: string;
  subject: string;
}

export interface GitBranch {
  name: string;
  current: boolean;
}

export interface GitBranches {
  current: string;
  branches: GitBranch[];
}

export interface GitActionResult {
  status: string;
  path?: string;
  commit?: string;
  output?: string;
  remote?: string;
  branch?: string | null;
  url?: string;
}

export interface ProjectEnvironment {
  runtime: { type: string; dockerfile: string; image: string; gpu: boolean };
  dependency_file: string;
  dependency_file_exists: boolean;
  dependencies: string[];
  environment: Record<string, string>;
}

export type SettingsMap = Record<string, unknown>;

export interface CodeGraphNode {
  id: string;
  kind: string;
  label: string;
  file_path: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface CodeGraphEdge {
  source: string;
  target: string;
  kind: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface CodeGraphSummary {
  node_count: number;
  edge_count: number;
  components: Record<string, number>;
  languages: Record<string, number>;
  hotspots: { id: string; label: string; kind: string; degree: number; file_path: string }[];
  risks: string[];
}

export interface CodeGraph {
  project_id: string;
  project_path: string;
  nodes: CodeGraphNode[];
  edges: CodeGraphEdge[];
  summary: CodeGraphSummary;
}

export interface CodeGraphInspection {
  node: CodeGraphNode;
  incoming: CodeGraphEdge[];
  outgoing: CodeGraphEdge[];
  graph: CodeGraph;
}

export interface ComposeStatus {
  available: boolean;
  binary: string;
  compose_file: string | null;
  detected: boolean;
  services: { name: string; service: string; state: string; ports: string | unknown[] }[];
  error: string;
}

export interface LocationRow {
  id: string;
  name: string;
  type: string;
  host: string;
  user: string | null;
  project_root: string | null;
  runtime: string;
  gpu: number;
  created_at: string;
}

export interface LocationStatus {
  name: string;
  host: string;
  user: string | null;
  gpu_configured: boolean;
  reachable: boolean;
  docker_available: boolean;
  docker_version: string;
  gpu_available: boolean;
  gpu_name: string;
  error: string;
}

export interface AppStatus {
  app_id: string;
  name: string;
  port: number | null;
  url: string;
  url_path: string;
  log_path: string;
  container_running: boolean;
  state: string;
  pid: number | null;
  alive: boolean | null;
}

export function listProjects(): Promise<ProjectRow[]> {
  return request("/projects");
}

export function getProject(id: string): Promise<ProjectDetail> {
  return request(`/projects/${id}`);
}

export function createProject(name: string, template: string): Promise<{ project_id: string; name: string; path: string }> {
  return request("/projects", { method: "POST", body: JSON.stringify({ name, template }) });
}

export function buildProject(id: string): Promise<BuildResult> {
  return request(`/projects/${id}/build`, { method: "POST" });
}

export function startProject(id: string): Promise<{ status: string; container: string }> {
  return request(`/projects/${id}/start`, { method: "POST" });
}

export function stopProject(id: string): Promise<{ status: string; container: string }> {
  return request(`/projects/${id}/stop`, { method: "POST" });
}

export function projectStatus(id: string): Promise<ProjectStatus> {
  return request(`/projects/${id}/status`);
}

export function projectEnvironment(id: string): Promise<ProjectEnvironment> {
  return request(`/projects/${id}/environment`);
}

export function addProjectDependency(id: string, dependency: string): Promise<ProjectEnvironment> {
  return request(`/projects/${id}/environment/dependencies`, { method: "POST", body: JSON.stringify({ dependency }) });
}

export function setProjectEnvironmentVariable(id: string, name: string, value: string): Promise<ProjectEnvironment> {
  return request(`/projects/${id}/environment/variables`, { method: "POST", body: JSON.stringify({ name, value }) });
}

export function removeProjectEnvironmentVariable(id: string, name: string): Promise<ProjectEnvironment> {
  return request(`/projects/${id}/environment/variables/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export function getProjectGraph(projectId: string): Promise<CodeGraph> {
  return request(`/projects/${projectId}/graph`);
}

export function indexProjectGraph(projectId: string): Promise<CodeGraph> {
  return request(`/projects/${projectId}/graph/index`, { method: "POST" });
}

export function projectGraphSummary(projectId: string): Promise<{ project_id: string; project_name: string } & CodeGraphSummary> {
  return request(`/projects/${projectId}/graph/summary`);
}

export function searchProjectGraph(projectId: string, query: string, kind?: string, limit = 25): Promise<CodeGraph> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (kind) params.set("kind", kind);
  return request(`/projects/${projectId}/graph/search?${params.toString()}`);
}

export function inspectProjectGraphNode(projectId: string, nodeId: string, depth = 1): Promise<CodeGraphInspection> {
  return request(`/projects/${projectId}/graph/nodes/${encodeURIComponent(nodeId)}?depth=${depth}`);
}

export function gitStatus(projectId: string): Promise<GitStatus> {
  return request(`/projects/${projectId}/git/status`);
}

export function gitInit(projectId: string): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/init`, { method: "POST" });
}

export function gitHistory(projectId: string, limit = 8): Promise<GitCommit[]> {
  return request(`/projects/${projectId}/git/history?limit=${limit}`);
}

export function gitBranches(projectId: string): Promise<GitBranches> {
  return request(`/projects/${projectId}/git/branches`);
}

export function gitSwitchBranch(projectId: string, branch: string, create = false): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/branches`, { method: "POST", body: JSON.stringify({ branch, create }) });
}

export function gitCommit(projectId: string, message: string, allChanges = true): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/commit`, { method: "POST", body: JSON.stringify({ message, all_changes: allChanges }) });
}

export function gitFetch(projectId: string, remote = "origin"): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/fetch`, { method: "POST", body: JSON.stringify({ remote }) });
}

export function gitPull(projectId: string, remote = "origin", branch?: string): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/pull`, { method: "POST", body: JSON.stringify({ remote, branch }) });
}

export function gitPush(projectId: string, remote = "origin", branch?: string, setUpstream = false): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/push`, {
    method: "POST",
    body: JSON.stringify({ remote, branch, set_upstream: setUpstream }),
  });
}

export function gitPublish(projectId: string, remoteUrl: string, remote = "origin", branch?: string): Promise<GitActionResult> {
  return request(`/projects/${projectId}/git/publish`, {
    method: "POST",
    body: JSON.stringify({ remote_url: remoteUrl, remote, branch }),
  });
}

export function startApp(projectId: string, appId: string): Promise<{ status: string; app: string; pid: number; url: string }> {
  return request(`/projects/${projectId}/apps/${appId}/start`, { method: "POST" });
}

export function stopApp(projectId: string, appId: string): Promise<{ status: string; app: string }> {
  return request(`/projects/${projectId}/apps/${appId}/stop`, { method: "POST" });
}

export function appStatus(projectId: string, appId: string): Promise<AppStatus> {
  return request(`/projects/${projectId}/apps/${appId}/status`);
}

export function projectLogs(projectId: string, tail = 100): Promise<{ logs: string }> {
  return request(`/projects/${projectId}/logs?tail=${tail}`);
}

export function appLogs(projectId: string, appId: string, tail = 50): Promise<{ logs: string; app_id: string }> {
  return request(`/projects/${projectId}/apps/${appId}/logs?tail=${tail}`);
}

export function composeStatus(projectId: string): Promise<ComposeStatus> {
  return request(`/projects/${projectId}/compose/status`);
}

export function composeUp(projectId: string, build = false): Promise<{ status: string; compose_file: string }> {
  return request(`/projects/${projectId}/compose/up?build=${build}`, { method: "POST" });
}

export function composeDown(projectId: string): Promise<{ status: string; compose_file: string }> {
  return request(`/projects/${projectId}/compose/down`, { method: "POST" });
}

export function composeLogs(projectId: string, tail = 50): Promise<{ logs: string }> {
  return request(`/projects/${projectId}/compose/logs?tail=${tail}`);
}

export function listLocations(): Promise<LocationRow[]> {
  return request("/locations");
}

export function locationStatus(name: string): Promise<LocationStatus> {
  return request(`/locations/${encodeURIComponent(name)}/status`);
}

export interface DoctorStatus {
  docker: {
    available: boolean;
    binary_found: boolean;
    daemon_running: boolean;
    socket_accessible: boolean;
    version: string;
    error: string;
  };
  gpu: {
    available: boolean;
    name: string;
    vram_mb: number;
  };
}

export interface DoctorCheckItem {
  label: string;
  severity: "info" | "warning" | "error" | "critical";
  ok: boolean;
  detail: string;
  suggestion: string;
}

export interface DoctorReport {
  project_name: string;
  project_path: string;
  all_ok: boolean;
  checks: DoctorCheckItem[];
}

export interface ResourceSnapshot {
  id: number;
  project_id: string;
  timestamp: string;
  cpu_percent: number | null;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  memory_percent: number | null;
  disk_used_gb: number | null;
  disk_total_gb: number | null;
  disk_percent: number | null;
  containers: ResourceContainer[];
  apps: ResourceApp[];
  compose_services: ResourceComposeService[];
}

export interface ResourceContainer {
  id: number;
  snapshot_id: number;
  container_name: string;
  cpu_percent: number | null;
  memory_used_mb: number | null;
  memory_limit_mb: number | null;
  memory_percent: number | null;
  network_rx_bytes: number | null;
  network_tx_bytes: number | null;
  block_read_bytes: number | null;
  block_write_bytes: number | null;
}

export interface ResourceApp {
  id: number;
  snapshot_id: number;
  app_id: string;
  app_name: string;
  cpu_percent: number | null;
  memory_used_mb: number | null;
  memory_limit_mb: number | null;
  memory_percent: number | null;
}

export interface ResourceComposeService {
  id: number;
  snapshot_id: number;
  service_name: string;
  cpu_percent: number | null;
  memory_used_mb: number | null;
  memory_limit_mb: number | null;
  memory_percent: number | null;
  network_rx_bytes: number | null;
  network_tx_bytes: number | null;
  health_status: string | null;
}

export interface BuildLogEntry {
  id: number;
  project_id: string;
  image: string;
  status: string;
  logs: string;
  built_at: string;
}

export interface BuildResult {
  status: string;
  image: string;
  warnings: string[];
  build_logs: string;
}

export function doctorCheck(): Promise<DoctorStatus> {
  return request("/doctor");
}

export function projectDoctor(projectId: string): Promise<DoctorReport> {
  return request(`/projects/${projectId}/doctor`);
}

export function projectBuildLogs(projectId: string, limit = 5): Promise<BuildLogEntry[]> {
  return request(`/projects/${projectId}/build/logs?limit=${limit}`);
}

export function createLocation(data: { name: string; host: string; user?: string | null; project_root?: string | null; runtime?: string; gpu?: boolean }): Promise<LocationRow> {
  return request("/locations", { method: "POST", body: JSON.stringify(data) });
}

export function deleteLocation(name: string): Promise<{ status: string; name: string }> {
  return request(`/locations/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export interface CurrentResourceUsage {
  cpu_percent: number | null;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  memory_percent: number | null;
  disk_used_gb: number | null;
  disk_total_gb: number | null;
  disk_percent: number | null;
}

export function getCurrentResources(projectId: string): Promise<{ project_id: string; system: CurrentResourceUsage; project: CurrentResourceUsage; timestamp: string }> {
  return request(`/projects/${projectId}/resources/current`);
}

export function getResourceHistory(projectId: string, limit?: number): Promise<{ project_id: string; history: ResourceSnapshot[]; count: number }> {
  const queryParams = limit ? `?limit=${limit}` : '';
  return request(`/projects/${projectId}/resources/history${queryParams}`);
}

export function getLatestResourceSnapshot(projectId: string): Promise<{ project_id: string; snapshot: ResourceSnapshot }> {
  return request(`/projects/${projectId}/resources/snapshot`);
}

export function collectResourceSnapshot(projectId: string): Promise<{ project_id: string; snapshot_id: number; message: string }> {
  return request(`/projects/${projectId}/resources/collect`, { method: "POST" });
}

export function listSettings(): Promise<SettingsMap> {
  return request("/settings");
}

export function getSetting(key: string): Promise<{ key: string; value: unknown }> {
  return request(`/settings/${encodeURIComponent(key)}`);
}

export function setSetting(key: string, value: unknown): Promise<{ key: string; value: unknown }> {
  return request(`/settings/${encodeURIComponent(key)}`, { method: "PUT", body: JSON.stringify({ value }) });
}

export function removeSetting(key: string): Promise<{ removed: boolean; key: string }> {
  return request(`/settings/${encodeURIComponent(key)}`, { method: "DELETE" });
}
