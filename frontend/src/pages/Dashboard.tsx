import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listProjects, ProjectRow } from "../api";
import StatusDot from "../components/StatusDot";
import { AlertIcon, BoxIcon, ChevronRightIcon, PlusIcon, RefreshIcon } from "../components/icons";

function timeAgo(value: string) {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.floor(elapsed / 60_000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

function ProjectRowView({ project }: { project: ProjectRow }) {
  return (
    <Link to={`/project/${project.id}`} className="data-row group">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <StatusDot status={project.container_running ? "running" : "stopped"} />
          <h2 className="truncate text-xl font-black">{project.name}</h2>
        </div>
        <div className="mt-2 truncate font-mono text-sm text-[var(--muted)]">{project.path}</div>
      </div>
      <div className="flex items-center gap-4 justify-self-end">
        <div className="text-right">
          <div className="eyebrow">updated</div>
          <div className="mt-1 font-mono text-sm font-bold">{timeAgo(project.updated_at)}</div>
        </div>
        <ChevronRightIcon className="h-5 w-5 text-[var(--muted)] transition-transform group-hover:translate-x-1" />
      </div>
    </Link>
  );
}

export default function Dashboard() {
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setProjects(await listProjects());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const stats = useMemo(() => {
    const running = projects.filter((p) => p.container_running).length;
    return {
      total: projects.length,
      running,
      stopped: projects.length - running,
    };
  }, [projects]);

  return (
    <div className="page-pad">
      <section className="grid gap-6 border-b border-[rgba(24,26,31,0.16)] pb-8 lg:grid-cols-[1fr_auto]">
        <div>
          <div className="eyebrow">workspace inventory</div>
          <h1 className="section-title mt-3">Projects</h1>
        </div>
        <div className="flex items-start gap-2 lg:pt-8">
          <button onClick={refresh} className="ghost-button" disabled={loading}>
            <RefreshIcon />
            Refresh
          </button>
          <Link to="/new" className="command-button">
            <PlusIcon />
            New
          </Link>
        </div>
      </section>

      <section className="grid gap-3 py-6 sm:grid-cols-3">
        <div className="metric">
          <div className="eyebrow">total</div>
          <div className="mt-2 text-4xl font-black">{stats.total}</div>
        </div>
        <div className="metric metric-active">
          <div className="eyebrow">running</div>
          <div className="mt-2 text-4xl font-black">{stats.running}</div>
        </div>
        <div className="metric metric-warn">
          <div className="eyebrow">stopped</div>
          <div className="mt-2 text-4xl font-black">{stats.stopped}</div>
        </div>
      </section>

      {error && (
        <div className="mb-6 flex items-start gap-3 border border-[rgba(182,75,61,0.35)] bg-[rgba(182,75,61,0.08)] p-4 text-sm text-[var(--coral)]">
          <AlertIcon className="mt-0.5 h-4 w-4 flex-none" />
          <span className="font-mono">{error}</span>
        </div>
      )}

      <section className="panel p-5">
        {loading ? (
          <div className="flex items-center gap-3 py-10 font-mono text-sm text-[var(--muted)]">
            <RefreshIcon className="h-4 w-4 animate-spin" />
            loading projects
          </div>
        ) : projects.length === 0 ? (
          <div className="grid place-items-center py-16 text-center">
            <BoxIcon className="h-10 w-10 text-[var(--muted)]" />
            <h2 className="mt-5 text-2xl font-black">No projects</h2>
            <Link to="/new" className="command-button mt-6">
              <PlusIcon />
              Create
            </Link>
          </div>
        ) : (
          <div>
            {projects.map((project) => (
              <ProjectRowView key={project.id} project={project} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
