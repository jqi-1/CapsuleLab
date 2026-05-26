export default function LogViewer({ logs, loading }: { logs: string; loading?: boolean }) {
  const lines = logs ? logs.split("\n").filter(Boolean) : [];

  return (
    <div className="log-terminal">
      {loading ? (
        <span className="text-[#89919f]">capturing...</span>
      ) : lines.length > 0 ? (
        <div className="space-y-0.5">
          {lines.map((line, i) => (
            <div key={`${i}-${line.slice(0, 12)}`} className="flex min-w-0">
              <span className="line-number">{String(i + 1).padStart(3, "0")}</span>
              <span className="whitespace-pre-wrap break-words">{line}</span>
            </div>
          ))}
        </div>
      ) : (
        <span className="text-[#89919f]">no log lines</span>
      )}
    </div>
  );
}
