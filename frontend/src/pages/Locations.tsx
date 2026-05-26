import { useEffect, useState } from "react";
import {
  createLocation,
  deleteLocation,
  listLocations,
  locationStatus,
  LocationRow,
  LocationStatus,
} from "../api";
import StatusDot from "../components/StatusDot";
import { AlertIcon, GlobeIcon, PlusIcon, RefreshIcon, TrashIcon } from "../components/icons";

export default function Locations() {
  const [locations, setLocations] = useState<LocationRow[]>([]);
  const [statuses, setStatuses] = useState<Record<string, LocationStatus>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: "", host: "", user: "", project_root: "", gpu: false });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function fetchLocations() {
    setLoading(true);
    setError(null);
    try {
      const locs = await listLocations();
      setLocations(locs);
      const results = await Promise.all(
        locs.map(async (loc) => {
          try {
            return [loc.name, await locationStatus(loc.name)] as const;
          } catch {
            return [loc.name, null] as const;
          }
        }),
      );
      setStatuses(Object.fromEntries(results.filter(([, status]) => status !== null) as [string, LocationStatus][]));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load locations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLocations();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createLocation({
        name: formData.name,
        host: formData.host,
        user: formData.user || null,
        project_root: formData.project_root || null,
        gpu: formData.gpu,
      });
      setShowForm(false);
      setFormData({ name: "", host: "", user: "", project_root: "", gpu: false });
      await fetchLocations();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create location");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(name: string) {
    setDeleting(name);
    setError(null);
    try {
      await deleteLocation(name);
      await fetchLocations();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete location");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="page-pad">
      <section className="grid gap-6 border-b border-[rgba(24,26,31,0.16)] pb-8 lg:grid-cols-[1fr_auto]">
        <div>
          <div className="eyebrow">remote targets</div>
          <h1 className="section-title mt-3">Locations</h1>
        </div>
        <div className="flex items-start gap-2 lg:pt-8">
          <button onClick={fetchLocations} className="ghost-button" disabled={loading}>
            <RefreshIcon className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </button>
          <button onClick={() => setShowForm((value) => !value)} className="command-button">
            <PlusIcon />
            {showForm ? "Close" : "Add"}
          </button>
        </div>
      </section>

      {error && (
        <div className="my-6 flex items-start gap-3 border border-[rgba(182,75,61,0.35)] bg-[rgba(182,75,61,0.08)] p-4 text-sm text-[var(--coral)]">
          <AlertIcon className="mt-0.5 h-4 w-4 flex-none" />
          <span className="font-mono">{error}</span>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="panel my-6 p-5">
          <div className="eyebrow">new location</div>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label>
              <span className="mb-2 block text-sm font-black">Name</span>
              <input className="field" value={formData.name} onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))} placeholder="lab-server" required />
            </label>
            <label>
              <span className="mb-2 block text-sm font-black">Host</span>
              <input className="field" value={formData.host} onChange={(e) => setFormData((p) => ({ ...p, host: e.target.value }))} placeholder="192.168.1.20" required />
            </label>
            <label>
              <span className="mb-2 block text-sm font-black">User</span>
              <input className="field" value={formData.user} onChange={(e) => setFormData((p) => ({ ...p, user: e.target.value }))} placeholder="ubuntu" />
            </label>
            <label>
              <span className="mb-2 block text-sm font-black">Project root</span>
              <input className="field" value={formData.project_root} onChange={(e) => setFormData((p) => ({ ...p, project_root: e.target.value }))} placeholder="~/capsulelab-projects" />
            </label>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2 font-bold">
              <input
                type="checkbox"
                checked={formData.gpu}
                onChange={(e) => setFormData((p) => ({ ...p, gpu: e.target.checked }))}
                className="h-4 w-4 accent-[var(--cyan)]"
              />
              GPU
            </label>
            <button type="submit" disabled={saving || !formData.name || !formData.host} className="command-button">
              <PlusIcon />
              {saving ? "Saving" : "Save"}
            </button>
          </div>
        </form>
      )}

      <section className="panel mt-6 p-5">
        {loading ? (
          <div className="flex items-center gap-3 py-10 font-mono text-sm text-[var(--muted)]">
            <RefreshIcon className="h-4 w-4 animate-spin" />
            checking locations
          </div>
        ) : locations.length === 0 ? (
          <div className="grid place-items-center py-16 text-center">
            <GlobeIcon className="h-10 w-10 text-[var(--muted)]" />
            <h2 className="mt-5 text-2xl font-black">No locations</h2>
          </div>
        ) : (
          <div>
            {locations.map((loc) => {
              const status = statuses[loc.name];
              return (
                <div key={loc.id} className="data-row">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-3">
                      <StatusDot status={status?.reachable ? "alive" : "dead"} />
                      <h2 className="truncate text-xl font-black">{loc.name}</h2>
                      <span className="font-mono text-sm text-[var(--muted)]">
                        {loc.user ? `${loc.user}@${loc.host}` : loc.host}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-sm text-[var(--muted)]">
                      <span>{loc.project_root || "default project root"}</span>
                      <span>{status?.docker_version ? `Docker ${status.docker_version}` : status?.docker_available ? "Docker OK" : "Docker unavailable"}</span>
                      <span>{status?.gpu_available ? status.gpu_name : loc.gpu ? "GPU requested" : "CPU"}</span>
                    </div>
                    {status?.error && <div className="mt-2 font-mono text-sm text-[var(--coral)]">{status.error}</div>}
                  </div>
                  <button onClick={() => handleDelete(loc.name)} disabled={deleting === loc.name} className="danger-button justify-self-end">
                    <TrashIcon />
                    {deleting === loc.name ? "Deleting" : "Delete"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
