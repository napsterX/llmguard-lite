const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Stats {
  total_requests: number;
  allowed_count: number;
  blocked_count: number;
  avg_latency_ms: number;
}

interface LogEntry {
  id: string;
  created_at: string | null;
  provider: string;
  model: string;
  allowed: boolean;
  policy_name: string;
  policy_severity: string;
  upstream_status_code: number | null;
  latency_ms: number | null;
}

async function fetchStats(): Promise<Stats | null> {
  try {
    const res = await fetch(`${API}/admin/stats`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchLogs(): Promise<LogEntry[]> {
  try {
    const res = await fetch(`${API}/admin/logs?limit=20`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.logs ?? [];
  } catch {
    return [];
  }
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-6 py-5 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
      <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{value}</p>
      {sub && <p className="mt-1 text-xs text-zinc-400">{sub}</p>}
    </div>
  );
}

export default async function Home() {
  const [stats, logs] = await Promise.all([fetchStats(), fetchLogs()]);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 font-sans">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center gap-3">
          <span className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">LLMGuard Lite</span>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
            OSS
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8 space-y-8">
        {/* Stats */}
        <section>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-zinc-400">Overview</h2>
          {stats ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatCard label="Total Requests" value={stats.total_requests.toLocaleString()} />
              <StatCard label="Allowed" value={stats.allowed_count.toLocaleString()} />
              <StatCard label="Blocked" value={stats.blocked_count.toLocaleString()} />
              <StatCard label="Avg Latency" value={`${stats.avg_latency_ms} ms`} />
            </div>
          ) : (
            <p className="text-sm text-zinc-400">Could not reach backend at {API}</p>
          )}
        </section>

        {/* Logs */}
        <section>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-zinc-400">Recent Requests</h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
            <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-700">
              <thead>
                <tr className="bg-zinc-50 dark:bg-zinc-800">
                  {["Time", "Provider", "Model", "Status", "Policy", "Latency"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-zinc-400">
                      No requests logged yet.
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-500 dark:text-zinc-400">
                        {log.created_at ? new Date(log.created_at).toLocaleTimeString() : "—"}
                      </td>
                      <td className="px-4 py-3 font-medium text-zinc-700 dark:text-zinc-300 capitalize">
                        {log.provider}
                      </td>
                      <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400 font-mono text-xs">
                        {log.model}
                      </td>
                      <td className="px-4 py-3">
                        {log.allowed ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                            allowed
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                            blocked
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400 font-mono text-xs">
                        {log.policy_name === "none" ? "—" : log.policy_name}
                      </td>
                      <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400">
                        {log.latency_ms != null ? `${log.latency_ms} ms` : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
