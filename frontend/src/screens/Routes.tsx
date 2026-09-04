import { useEffect, useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { api } from "../api";
import { Empty, Status } from "../components";
type Route = {
  method: string;
  path: string;
  summary: string;
  capability: string | null;
  authenticated: boolean;
  availability: string;
};
export function Routes() {
  const [items, setItems] = useState<Route[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Route[]>("/routes")
      .then(setItems)
      .catch((reason: Error) => setError(reason.message));
  }, []);
  return (
    <>
      <header className="mb-7">
        <p className="text-sm font-semibold text-blue-600">OPENAPI</p>
        <h1 className="mt-1 text-3xl font-bold">Rotas</h1>
        <p className="mt-2 text-slate-500">
          Inventário derivado do contrato publicado pelo runtime.
        </p>
      </header>
      <div className="panel overflow-x-auto">
        {error ? (
          <Empty>Não foi possível carregar as rotas: {error}</Empty>
        ) : items.length ? (
          <table>
            <thead>
              <tr>
                <th>Método</th>
                <th>Path</th>
                <th>Capability</th>
                <th>Autenticação</th>
                <th>Disponibilidade</th>
                <th>Descrição</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={`${r.method}-${r.path}`}>
                  <td>
                    <span className="badge bg-blue-50 font-mono text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                      {r.method}
                    </span>
                  </td>
                  <td className="font-mono font-semibold">{r.path}</td>
                  <td>{r.capability ?? "core"}</td>
                  <td>
                    {r.authenticated ? (
                      <span className="flex items-center gap-1.5 text-emerald-600">
                        <Lock size={14} />
                        Bearer
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-slate-500">
                        <Unlock size={14} />
                        Pública
                      </span>
                    )}
                  </td>
                  <td>
                    <Status value={r.availability} />
                  </td>
                  <td className="text-slate-500">{r.summary || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>Nenhuma rota publicada.</Empty>
        )}
      </div>
    </>
  );
}
