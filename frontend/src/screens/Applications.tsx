import { Pencil, Plus } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { Field, Modal, Status } from "../components";

type App = {
  id: string;
  display_name: string;
  client_id: string;
  state: "active" | "disabled" | "reserved";
  protected: boolean;
  capabilities: string[];
  quotas: Record<string, number>;
};

export function Applications() {
  const [apps, setApps] = useState<App[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<App>();
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const load = () => {
    setLoading(true);
    setPageError("");
    return api<App[]>("/applications")
      .then(setApps)
      .catch((error: Error) => setPageError(error.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    void load();
  }, []);
  return (
    <>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-blue-600">REGISTRY</p>
          <h1 className="mt-1 text-3xl font-bold">Aplicações</h1>
          <p className="mt-2 text-slate-500">
            Identidades, capabilities e limites de acesso.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          <Plus size={17} />
          Nova aplicação
        </button>
      </div>
      {pageError && (
        <div className="mb-5 rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
          Não foi possível carregar o registry: {pageError}
        </div>
      )}
      <div className="panel overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Aplicação</th>
              <th>Estado</th>
              <th>Capabilities</th>
              <th>Quotas/min</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="py-10 text-center text-slate-500">
                  Carregando aplicações…
                </td>
              </tr>
            )}
            {!loading && !pageError && apps.length === 0 && (
              <tr>
                <td colSpan={5} className="py-10 text-center text-slate-500">
                  Nenhuma aplicação cadastrada.
                </td>
              </tr>
            )}
            {apps.map((app) => (
              <tr key={app.id}>
                <td>
                  <b>{app.display_name}</b>
                  <div className="font-mono text-xs text-slate-500">
                    {app.id}
                  </div>
                </td>
                <td>
                  <Status value={app.state} />
                </td>
                <td>
                  {app.capabilities.length
                    ? app.capabilities.map((c) => (
                        <span
                          className="badge mr-1 bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
                          key={c}
                        >
                          {c}
                        </span>
                      ))
                    : "—"}
                </td>
                <td>
                  {app.capabilities.map((c) => (
                    <div key={c}>
                      {c}: {app.quotas[c] ?? "—"}
                    </div>
                  ))}
                </td>
                <td>
                  <button
                    className="btn-secondary !p-2"
                    onClick={() => setEditing(app)}
                  >
                    <Pencil size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Create
        open={open}
        close={() => setOpen(false)}
        done={() => {
          setOpen(false);
          void load();
        }}
      />
      <Edit
        app={editing}
        close={() => setEditing(undefined)}
        done={() => {
          setEditing(undefined);
          void load();
        }}
      />
    </>
  );
}

function Create({
  open,
  close,
  done,
}: {
  open: boolean;
  close: () => void;
  done: () => void;
}) {
  const [error, setError] = useState("");
  return (
    <Modal
      open={open}
      onOpenChange={(v) => !v && close()}
      title="Nova aplicação"
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          try {
            await api("/applications", {
              method: "POST",
              body: JSON.stringify({
                id: f.get("id"),
                display_name: f.get("name"),
                client_id: f.get("client"),
              }),
            });
            done();
          } catch (x) {
            setError((x as Error).message);
          }
        }}
      >
        <Field label="ID canônico">
          <input
            className="input"
            name="id"
            placeholder="minha_aplicacao"
            required
          />
        </Field>
        <Field label="Nome">
          <input className="input" name="name" required />
        </Field>
        <Field label="Client ID">
          <input className="input" name="client" required />
        </Field>
        <p className="text-xs text-slate-500">
          A aplicação nasce desabilitada. Crie uma credencial e configure quotas
          antes de ativar.
        </p>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button className="btn-primary w-full">Criar aplicação</button>
      </form>
    </Modal>
  );
}

function Edit({
  app,
  close,
  done,
}: {
  app?: App;
  close: () => void;
  done: () => void;
}) {
  const [error, setError] = useState("");
  if (!app) return null;
  return (
    <Modal
      open
      onOpenChange={(v) => !v && close()}
      title={`Editar ${app.display_name}`}
    >
      <form
        className="space-y-4"
        onSubmit={async (e: FormEvent<HTMLFormElement>) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const caps = ["ai", "search"].filter((c) => f.get(c));
          const quotas = Object.fromEntries(
            caps.map((c) => [c, Number(f.get(`${c}_quota`))]),
          );
          try {
            await api(`/applications/${app.id}`, {
              method: "PUT",
              body: JSON.stringify({
                display_name: f.get("name"),
                state: f.get("state"),
                capabilities: caps,
                quotas,
              }),
            });
            done();
          } catch (x) {
            setError((x as Error).message);
          }
        }}
      >
        <Field label="Nome">
          <input
            className="input"
            name="name"
            defaultValue={app.display_name}
          />
        </Field>
        <Field label="Estado">
          <select
            className="input"
            name="state"
            defaultValue={app.state}
            disabled={app.protected}
          >
            <option value="disabled">Disabled</option>
            <option value="active">Active</option>
          </select>
        </Field>
        {["ai", "search"].map((c) => (
          <div className="grid grid-cols-[1fr_110px] items-end gap-3" key={c}>
            <label className="flex gap-2 py-2">
              <input
                type="checkbox"
                name={c}
                defaultChecked={app.capabilities.includes(c)}
                disabled={app.protected}
              />
              {c.toUpperCase()}
            </label>
            <Field label="por minuto">
              <input
                className="input"
                type="number"
                min="1"
                name={`${c}_quota`}
                defaultValue={app.quotas[c] ?? 60}
                disabled={app.protected}
              />
            </Field>
          </div>
        ))}
        {app.protected && (
          <p className="text-sm text-amber-600">
            Aplicação reservada e protegida por invariante.
          </p>
        )}
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button className="btn-primary w-full" disabled={app.protected}>
          Salvar
        </button>
      </form>
    </Modal>
  );
}
