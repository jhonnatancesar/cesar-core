import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { Check, Copy, KeyRound, Plus, ShieldX } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Field, Modal, Status } from "../components";
type Credential = {
  id: string;
  application_id: string;
  name: string;
  fingerprint: string | null;
  created_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  read_only?: boolean;
};
type App = { id: string; display_name: string };
export function Credentials() {
  const [items, setItems] = useState<Credential[]>([]);
  const [apps, setApps] = useState<App[]>([]);
  const [open, setOpen] = useState(false);
  const [secret, setSecret] = useState("");
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [createError, setCreateError] = useState("");
  const load = () => {
    setLoading(true);
    setPageError("");
    Promise.all([
      api<Credential[]>("/credentials"),
      api<App[]>("/applications"),
    ])
      .then(([credentials, applications]) => {
        setItems(credentials);
        setApps(applications);
      })
      .catch((error: Error) => setPageError(error.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  return (
    <>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-blue-600">ACCESS</p>
          <h1 className="mt-1 text-3xl font-bold">Chaves de API</h1>
          <p className="mt-2 text-slate-500">
            Rotacione sem indisponibilidade; o segredo aparece uma única vez.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setOpen(true)}>
          <Plus size={17} />
          Nova chave
        </button>
      </div>
      {pageError && (
        <div className="mb-5 rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
          Não foi possível carregar as chaves: {pageError}
        </div>
      )}
      {secret && (
        <div className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-5 dark:border-amber-500/30 dark:bg-amber-500/10">
          <b>Copie agora. Esta chave não poderá ser exibida novamente.</b>
          <div className="mt-3 flex gap-2">
            <code className="min-w-0 flex-1 overflow-auto rounded-lg bg-slate-950 p-3 text-sm text-white">
              {secret}
            </code>
            <button
              className="btn-secondary"
              onClick={() => navigator.clipboard.writeText(secret)}
            >
              <Copy size={16} />
            </button>
          </div>
        </div>
      )}
      <div className="panel overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Aplicação</th>
              <th>Fingerprint</th>
              <th>Criada</th>
              <th>Último uso</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-slate-500">
                  Carregando chaves…
                </td>
              </tr>
            )}
            {!loading && !pageError && items.length === 0 && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-slate-500">
                  Nenhuma chave cadastrada.
                </td>
              </tr>
            )}
            {items.map((item) => (
              <tr key={item.id}>
                <td className="font-semibold">{item.name}</td>
                <td className="font-mono text-xs">{item.application_id}</td>
                <td className="font-mono text-xs">{item.fingerprint ?? "—"}</td>
                <td>
                  {item.created_at
                    ? new Date(item.created_at).toLocaleDateString()
                    : "—"}
                </td>
                <td>
                  {item.last_used_at
                    ? new Date(item.last_used_at).toLocaleString()
                    : "—"}
                </td>
                <td>
                  <Status value={item.revoked_at ? "revoked" : "active"} />
                  {item.revoked_at && (
                    <div className="mt-1 text-xs text-slate-500">
                      {new Date(item.revoked_at).toLocaleDateString()}
                    </div>
                  )}
                </td>
                <td>
                  {!item.read_only && !item.revoked_at && (
                    <Revoke id={item.id} done={load} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal open={open} onOpenChange={setOpen} title="Nova chave">
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            setCreateError("");
            try {
              const result = await api<{ credential: string }>("/credentials", {
                method: "POST",
                body: JSON.stringify({
                  application_id: f.get("application"),
                  name: f.get("name"),
                }),
              });
              setSecret(result.credential);
              setOpen(false);
              load();
            } catch (error) {
              setCreateError((error as Error).message);
            }
          }}
        >
          <Field label="Aplicação">
            <select className="input" name="application">
              {apps.map((a) => (
                <option value={a.id} key={a.id}>
                  {a.display_name}
                </option>
              ))}
            </select>
          </Field>
          {createError && (
            <p className="text-sm text-rose-600">{createError}</p>
          )}
          <Field label="Nome da chave">
            <input
              className="input"
              name="name"
              placeholder="Integração DEV"
              required
            />
          </Field>
          <button className="btn-primary w-full">
            <KeyRound size={17} />
            Gerar chave
          </button>
        </form>
      </Modal>
    </>
  );
}
function Revoke({ id, done }: { id: string; done: () => void }) {
  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger className="btn-secondary !p-2 text-rose-600">
        <ShieldX size={16} />
      </AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 bg-slate-950/55" />
        <AlertDialog.Content className="panel fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 p-6">
          <AlertDialog.Title className="text-xl font-bold">
            Revogar chave?
          </AlertDialog.Title>
          <AlertDialog.Description className="my-3 text-sm text-slate-500">
            A ação é imediata e não pode ser desfeita. Crie a substituta antes
            de revogar para uma rotação segura.
          </AlertDialog.Description>
          <div className="flex justify-end gap-2">
            <AlertDialog.Cancel className="btn-secondary">
              Cancelar
            </AlertDialog.Cancel>
            <AlertDialog.Action
              className="btn bg-rose-600 text-white"
              onClick={async () => {
                await api(`/credentials/${id}/revoke`, { method: "POST" });
                done();
              }}
            >
              <Check size={16} />
              Revogar
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
