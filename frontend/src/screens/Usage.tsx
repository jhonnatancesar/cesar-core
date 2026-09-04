import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty } from "../components";

type Row = {
  bucket_hour: string;
  application_id: string;
  capability: string;
  provider: string;
  cached: number;
  requests: number;
  tokens: number;
  queries: number;
};
type Quota = {
  application_id: string;
  capability: string;
  used: number | null;
  limit: number;
  ttl_seconds: number | null;
};
type UsageData = { rollups: Row[]; quotas: Quota[] };

export function Usage() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState<UsageData>();
  const [error, setError] = useState("");
  useEffect(() => {
    setError("");
    void api<UsageData>(`/usage?days=${days}`)
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, [days]);
  if (error) return <Empty>Não foi possível carregar o uso: {error}</Empty>;
  const totals = data?.rollups.reduce(
    (a, r) => ({
      requests: a.requests + r.requests,
      tokens: a.tokens + r.tokens,
      queries: a.queries + r.queries,
    }),
    { requests: 0, tokens: 0, queries: 0 },
  );
  return (
    <>
      <div className="mb-7 flex items-end justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-600">OBSERVABILITY</p>
          <h1 className="mt-1 text-3xl font-bold">Uso & quotas</h1>
          <p className="mt-2 text-slate-500">
            Rollups persistentes sem conteúdo de requisições.
          </p>
        </div>
        <select
          className="input !w-auto"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          <option value="1">24 horas</option>
          <option value="7">7 dias</option>
          <option value="30">30 dias</option>
        </select>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          ["Requests", totals?.requests ?? 0],
          ["Tokens", totals?.tokens ?? 0],
          ["Queries", totals?.queries ?? 0],
        ].map(([l, v]) => (
          <div className="panel p-5" key={l}>
            <p className="text-sm text-slate-500">{l}</p>
            <p className="mt-2 text-3xl font-bold">{v.toLocaleString()}</p>
          </div>
        ))}
      </div>
      <h2 className="mb-3 mt-7 text-lg font-bold">Janela atual</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {data?.quotas.map((q) => (
          <div
            className="panel p-5"
            key={`${q.application_id}-${q.capability}`}
          >
            <div className="flex justify-between">
              <b>
                {q.application_id} · {q.capability}
              </b>
              <span>
                {q.used ?? "—"} / {q.limit}
              </span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded bg-slate-100 dark:bg-slate-800">
              <div
                className="h-full rounded bg-blue-600"
                style={{
                  width: `${Math.min(100, ((q.used ?? 0) / q.limit) * 100)}%`,
                }}
              />
            </div>
            <p className="mt-2 text-xs text-slate-500">
              renova em {q.ttl_seconds ?? "—"}s
            </p>
          </div>
        ))}
      </div>
      <h2 className="mb-3 mt-7 text-lg font-bold">Rollups por hora</h2>
      <div className="panel overflow-x-auto">
        {data?.rollups.length ? (
          <table>
            <thead>
              <tr>
                <th>Hora</th>
                <th>Aplicação</th>
                <th>Capability</th>
                <th>Provider</th>
                <th>Requests</th>
                <th>Uso</th>
              </tr>
            </thead>
            <tbody>
              {data.rollups.map((r, i) => (
                <tr key={i}>
                  <td>{new Date(r.bucket_hour).toLocaleString()}</td>
                  <td>{r.application_id}</td>
                  <td>{r.capability}</td>
                  <td>
                    {r.provider || "—"}
                    {r.cached ? " · cache" : ""}
                  </td>
                  <td>{r.requests}</td>
                  <td>
                    {r.capability === "ai"
                      ? `${r.tokens} tokens`
                      : `${r.queries} queries`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>Nenhum uso agregado neste período.</Empty>
        )}
      </div>
    </>
  );
}
