import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../api";
import { AlertIcon, BoxIcon, CheckIcon, CpuIcon, PlusIcon } from "../components/icons";

const TEMPLATES = [
  { id: "python-basic", label: "Python Basic", desc: "Minimal Python data science workspace", tag: "PY" },
  { id: "pytorch-cuda", label: "PyTorch CUDA", desc: "GPU-enabled deep learning runtime", tag: "GPU" },
  { id: "streamlit-dashboard", label: "Streamlit Dashboard", desc: "Interactive app and data dashboard", tag: "APP" },
];

export default function CreateProject() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [template, setTemplate] = useState(TEMPLATES[0].id);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const result = await createProject(name.trim(), template);
      navigate(`/project/${result.project_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="page-pad">
      <section className="border-b border-[rgba(24,26,31,0.16)] pb-8">
        <div className="eyebrow">provision</div>
        <h1 className="section-title mt-3">New Project</h1>
      </section>

      <form onSubmit={handleSubmit} className="grid gap-6 py-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="panel p-5">
          <div className="eyebrow">identity</div>
          <label className="mt-5 block">
            <span className="mb-2 block text-sm font-black">Project name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="field font-mono text-lg"
              placeholder="experiment-runtime"
              required
              autoFocus
            />
          </label>

          <div className="mt-8">
            <div className="eyebrow">template</div>
            <div className="mt-4 grid gap-3">
              {TEMPLATES.map((item) => {
                const selected = template === item.id;
                return (
                  <label
                    key={item.id}
                    className={`grid cursor-pointer grid-cols-[3.5rem_1fr_auto] items-center gap-4 border p-4 transition ${
                      selected
                        ? "border-[var(--ink)] bg-[rgba(13,126,134,0.08)]"
                        : "border-[rgba(24,26,31,0.18)] bg-[rgba(255,252,245,0.54)] hover:border-[rgba(24,26,31,0.34)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="template"
                      value={item.id}
                      checked={selected}
                      onChange={() => setTemplate(item.id)}
                      className="sr-only"
                    />
                    <span className="grid h-12 place-items-center border border-[rgba(24,26,31,0.22)] bg-[var(--ink)] font-mono text-sm font-black text-[var(--paper)]">
                      {item.tag}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-lg font-black">{item.label}</span>
                      <span className="mt-1 block text-sm text-[var(--muted)]">{item.desc}</span>
                    </span>
                    {selected && <CheckIcon className="h-5 w-5 text-[var(--cyan)]" />}
                  </label>
                );
              })}
            </div>
          </div>
        </section>

        <aside className="panel-dark p-5">
          <div className="eyebrow !text-[#8c948f]">runtime order</div>
          <div className="mt-8 space-y-5">
            <div className="flex gap-3">
              <BoxIcon className="mt-1 h-5 w-5 text-[#cda16d]" />
              <div>
                <div className="font-black">Container workspace</div>
                <div className="mt-1 text-sm text-[#aeb6ad]">{name.trim() || "unnamed-project"}</div>
              </div>
            </div>
            <div className="flex gap-3">
              <CpuIcon className="mt-1 h-5 w-5 text-[#72bec5]" />
              <div>
                <div className="font-black">Template image</div>
                <div className="mt-1 text-sm text-[#aeb6ad]">{template}</div>
              </div>
            </div>
          </div>

          {error && (
            <div className="mt-8 flex gap-3 border border-[rgba(182,75,61,0.5)] bg-[rgba(182,75,61,0.14)] p-3 text-sm text-[#ffc5bc]">
              <AlertIcon className="h-4 w-4 flex-none" />
              <span className="font-mono">{error}</span>
            </div>
          )}

          <button type="submit" disabled={creating || !name.trim()} className="command-button mt-8 w-full !border-[#f4f0e7] !bg-[#f4f0e7] !text-[var(--ink)]">
            {creating ? (
              <>
                <CpuIcon className="h-4 w-4 animate-spin" />
                Creating
              </>
            ) : (
              <>
                <PlusIcon />
                Create Project
              </>
            )}
          </button>
        </aside>
      </form>
    </div>
  );
}
