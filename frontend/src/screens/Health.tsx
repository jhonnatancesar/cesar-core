import { useEffect, useState } from "react";
import { CheckCircle2, Clock3 } from "lucide-react";
import { api } from "../api";
import { Empty, Status } from "../components";
type Component = {
  name: string;
  status: string;
  checked_at: string;
  version?: string;
};
type Data = {
  status: string;
  reason?: string;
  checked_at: string;
  latency_ms: number;
  components: Component[];
};
export function Health() {
  const [data, setData] = useState<Data>();
  const [error, setError] = useState("");
  useEffect(() => {
    api<Data>("/health")
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, []);
  if (error) return <Empty>Não foi possível executar os probes: {error}</Empty>;
  if (!data) return <Empty>Executando probes reais…</Empty>;
  return (
    <>
      <header className="mb-7">
        <p className="text-sm font-semibold text-blue-600">RUNTIME</p>
        <h1 className="mt-1 text-3xl font-bold">Saúde</h1>
        <p className="mt-2 text-slate-500">
          Readiness detalhada sem exposição de configuração sensível.
        </p>
      </header>
      <section className="panel mb-5 flex flex-wrap items-center justify-between gap-4 p-6">
        <div className="flex items-center gap-3">
          <CheckCircle2
            className={
              data.status === "ok" ? "text-emerald-500" : "text-amber-500"
            }
          />
          <div>
            <b>Readiness global</b>
            <p className="text-sm text-slate-500">
              {data.reason ?? "Todos os requisitos habilitados responderam"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1 text-sm text-slate-500">
            <Clock3 size={15} />
            {data.latency_ms} ms
          </span>
          <Status value={data.status} />
        </div>
      </section>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.components.map((c) => (
          <article className="panel p-5" key={c.name}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-bold capitalize">
                  {c.name.replaceAll("_", " ")}
                </h2>
                {c.version && (
                  <p className="mt-1 font-mono text-xs text-slate-500">
                    v{c.version}
                  </p>
                )}
              </div>
              <Status value={c.status} />
            </div>
            <p className="mt-5 text-xs text-slate-500">
              Verificado em {new Date(c.checked_at).toLocaleTimeString()}
            </p>
          </article>
        ))}
      </div>
    </>
  );
}
