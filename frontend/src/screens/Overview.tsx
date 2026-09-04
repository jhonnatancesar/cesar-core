import { useEffect, useState } from "react";
import { AlertTriangle, AppWindow, Bot, Search } from "lucide-react";
import { api } from "../api";
import { Empty, Status } from "../components";

type Data = {
  version: string;
  uptime_seconds: number;
  applications: number;
  active_applications: number;
  credentials: number;
  ai_requests_24h: number;
  search_requests_24h: number;
  errors_24h: number;
  readiness: { status: string; reason?: string };
  dependencies: { name: string; status: string; reason?: string }[];
};
export function Overview() {
  const [data, setData] = useState<Data>();
  const [error, setError] = useState("");
  useEffect(() => {
    api<Data>("/overview")
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);
  if (error)
    return <Empty>Não foi possível carregar a visão geral: {error}</Empty>;
  if (!data) return <Empty>Carregando visão geral…</Empty>;
  const cards = [
    ["Aplicações", data.applications, AppWindow],
    ["AI · 24h", data.ai_requests_24h, Bot],
    ["Search · 24h", data.search_requests_24h, Search],
    ["Erros · 24h", data.errors_24h, AlertTriangle],
  ] as const;
  return (
    <>
      <header className="mb-7">
        <p className="text-sm font-semibold text-blue-600">CONTROL PLANE</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Visão geral</h1>
        <p className="mt-2 text-slate-500">
          Estado real da infraestrutura e dos consumidores.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value, Icon]) => (
          <div className="panel p-5" key={label}>
            <div className="mb-5 flex items-center justify-between text-slate-500">
              <span className="text-sm font-medium">{label}</span>
              <Icon size={19} />
            </div>
            <strong className="text-3xl">{value}</strong>
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <section className="panel p-6">
          <h2 className="text-lg font-bold">Dependências</h2>
          <div className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
            {data.dependencies.map((item) => (
              <div
                className="flex items-center justify-between py-3"
                key={item.name}
              >
                <div>
                  <p className="font-semibold capitalize">
                    {item.name.replaceAll("_", " ")}
                  </p>
                  {item.reason && (
                    <p className="text-xs text-slate-500">{item.reason}</p>
                  )}
                </div>
                <Status value={item.status} />
              </div>
            ))}
          </div>
        </section>
        <section className="panel p-6">
          <h2 className="text-lg font-bold">Runtime</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Versão</dt>
              <dd className="font-mono">{data.version}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Uptime</dt>
              <dd>{Math.floor(data.uptime_seconds / 60)} min</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Ativas</dt>
              <dd>{data.active_applications}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Credenciais</dt>
              <dd>{data.credentials}</dd>
            </div>
          </dl>
          <div className="mt-5 flex justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
            <b>Readiness</b>
            <Status value={data.readiness.status} />
          </div>
        </section>
      </div>
    </>
  );
}
