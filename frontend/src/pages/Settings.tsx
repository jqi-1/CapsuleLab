import { useEffect, useMemo, useState } from "react";
import { AlertIcon, RefreshIcon, SettingsIcon } from "../components/icons";
import { listSettings, removeSetting, setSetting, SettingsMap } from "../api";

const DEFAULT_SETTINGS: Record<string, string> = {
  "runtime.default": "docker",
  "paths.default_project_root": "",
  "proxy.base_url": "http://localhost:10000",
  "certificates.bundle": "",
};

type SettingKey = keyof typeof DEFAULT_SETTINGS;

type SettingSpec = {
  key: SettingKey;
  label: string;
  description: string;
  kind: "select" | "text";
  placeholder?: string;
  options?: { label: string; value: string }[];
  inputType?: string;
};

const SETTINGS: SettingSpec[] = [
  {
    key: "runtime.default",
    label: "Default runtime",
    description: "Used when a project is created without an explicit runtime.",
    kind: "select",
    options: [
      { label: "Docker", value: "docker" },
      { label: "Podman", value: "podman" },
    ],
  },
  {
    key: "paths.default_project_root",
    label: "Default project root",
    description: "Used when a new location does not provide its own project root.",
    kind: "text",
    placeholder: "/home/user/capsulelab-projects",
  },
  {
    key: "proxy.base_url",
    label: "Proxy base URL",
    description: "Used to build shareable links for local app proxies.",
    kind: "text",
    inputType: "url",
    placeholder: "http://localhost:10000",
  },
  {
    key: "certificates.bundle",
    label: "Certificate bundle",
    description: "Optional path to a CA bundle for remote TLS checks.",
    kind: "text",
    placeholder: "/etc/ssl/certs/ca-certificates.crt",
  },
];

function toText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function isDirty(key: SettingKey, current: string) {
  return current !== DEFAULT_SETTINGS[key];
}

export default function Settings() {
  const [values, setValues] = useState<SettingsMap>({});
  const [drafts, setDrafts] = useState<Record<SettingKey, string>>({
    "runtime.default": "",
    "paths.default_project_root": "",
    "proxy.base_url": "",
    "certificates.bundle": "",
  });
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<SettingKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const overrides = useMemo(() => {
    if (loading) return 0;
    return SETTINGS.filter((setting) => isDirty(setting.key, drafts[setting.key])).length;
  }, [drafts, loading]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const current = await listSettings();
      setValues(current);
      setDrafts(
        Object.fromEntries(SETTINGS.map((setting) => [setting.key, toText(current[setting.key])])) as Record<SettingKey, string>,
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSave(setting: SettingSpec) {
    const value = drafts[setting.key];
    setSavingKey(setting.key);
    setError(null);
    setNotice(null);
    try {
      if (setting.kind === "text" && value.trim() === "" && DEFAULT_SETTINGS[setting.key] === "") {
        await removeSetting(setting.key);
      } else {
        await setSetting(setting.key, value);
      }
      await refresh();
      setNotice(`${setting.label} saved`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save setting");
    } finally {
      setSavingKey(null);
    }
  }

  async function handleReset(setting: SettingSpec) {
    setSavingKey(setting.key);
    setError(null);
    setNotice(null);
    try {
      await removeSetting(setting.key);
      await refresh();
      setNotice(`${setting.label} reset`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to reset setting");
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <div className="page-pad">
      <section className="grid gap-6 border-b border-[rgba(24,26,31,0.16)] pb-8 lg:grid-cols-[1fr_auto]">
        <div>
          <div className="eyebrow">local preferences</div>
          <h1 className="section-title mt-3">Settings</h1>
        </div>
        <div className="flex items-start gap-2 lg:pt-8">
          <button onClick={refresh} className="ghost-button" disabled={loading}>
            <RefreshIcon className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </button>
        </div>
      </section>

      <section className="grid gap-3 py-6 sm:grid-cols-4">
        <div className="metric">
          <div className="eyebrow">keys</div>
          <div className="mt-2 text-4xl font-black">{SETTINGS.length}</div>
        </div>
        <div className="metric metric-active">
          <div className="eyebrow">edited</div>
          <div className="mt-2 text-4xl font-black">{overrides}</div>
        </div>
        <div className="metric metric-warn">
          <div className="eyebrow">runtime</div>
          <div className="mt-2 truncate text-2xl font-black">{drafts["runtime.default"] || DEFAULT_SETTINGS["runtime.default"]}</div>
        </div>
        <div className="metric">
          <div className="eyebrow">proxy</div>
          <div className="mt-2 truncate text-lg font-black">{drafts["proxy.base_url"] || DEFAULT_SETTINGS["proxy.base_url"]}</div>
        </div>
      </section>

      {error && (
        <div className="mb-6 flex items-start gap-3 border border-[rgba(182,75,61,0.35)] bg-[rgba(182,75,61,0.08)] p-4 text-sm text-[var(--coral)]">
          <AlertIcon className="mt-0.5 h-4 w-4 flex-none" />
          <span className="font-mono">{error}</span>
        </div>
      )}

      {notice && (
        <div className="mb-6 border border-[rgba(39,122,77,0.28)] bg-[rgba(39,122,77,0.08)] p-4 font-mono text-sm text-[var(--green)]">
          {notice}
        </div>
      )}

      <section className="panel p-5">
        {loading ? (
          <div className="flex items-center gap-3 py-10 font-mono text-sm text-[var(--muted)]">
            <RefreshIcon className="h-4 w-4 animate-spin" />
            loading settings
          </div>
        ) : (
          <div>
            {SETTINGS.map((setting) => {
              const value = drafts[setting.key];
              const dirty = isDirty(setting.key, value);
              const current = values[setting.key];

              return (
                <form
                  key={setting.key}
                  className="data-row items-start"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleSave(setting);
                  }}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-3">
                      <SettingsIcon className="h-4 w-4 text-[var(--muted)]" />
                      <h2 className="truncate text-xl font-black">{setting.label}</h2>
                      <span className="font-mono text-xs text-[var(--muted)]">{setting.key}</span>
                    </div>
                    <p className="mt-2 text-sm text-[var(--muted)]">{setting.description}</p>
                    <div className="mt-3 font-mono text-xs text-[var(--muted)]">
                      Current: {toText(current) || "empty"} | Default: {DEFAULT_SETTINGS[setting.key] || "empty"}
                    </div>
                  </div>

                  <div className="min-w-0 justify-self-stretch lg:min-w-[28rem]">
                    {setting.kind === "select" ? (
                      <select
                        className="field"
                        value={value}
                        onChange={(event) => setDrafts((previous) => ({ ...previous, [setting.key]: event.target.value }))}
                      >
                        {setting.options?.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="field"
                        type={setting.inputType ?? "text"}
                        value={value}
                        placeholder={setting.placeholder}
                        onChange={(event) => setDrafts((previous) => ({ ...previous, [setting.key]: event.target.value }))}
                      />
                    )}
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 font-mono text-xs text-[var(--muted)]">
                      <span>{dirty ? "edited" : "synced"}</span>
                      <span>{savingKey === setting.key ? "saving" : "ready"}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 justify-self-end pt-1">
                    <button type="button" onClick={() => void handleReset(setting)} disabled={savingKey === setting.key} className="ghost-button">
                      Reset
                    </button>
                    <button type="submit" disabled={!dirty || savingKey === setting.key} className="command-button">
                      {savingKey === setting.key ? <RefreshIcon className="h-4 w-4 animate-spin" /> : null}
                      Save
                    </button>
                  </div>
                </form>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
