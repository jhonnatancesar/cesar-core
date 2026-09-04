import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AppWindow,
  Gauge,
  HeartPulse,
  KeyRound,
  LogOut,
  Menu,
  Network,
  Plus,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, setCsrf } from "./api";
import { Applications } from "./screens/Applications";
import { Credentials } from "./screens/Credentials";
import { Health } from "./screens/Health";
import { Overview } from "./screens/Overview";
import { Routes } from "./screens/Routes";
import { Usage } from "./screens/Usage";
import { ThemeToggle } from "./components";

const navigation = [
  ["overview", "Visão geral", Gauge],
  ["applications", "Aplicações", AppWindow],
  ["credentials", "Chaves de API", KeyRound],
  ["usage", "Uso & quotas", Activity],
  ["routes", "Rotas", Network],
  ["health", "Saúde", HeartPulse],
] as const;

export function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [screen, setScreen] = useState(location.hash.slice(1) || "overview");
  const [dark, setDark] = useState(
    document.documentElement.classList.contains("dark"),
  );
  const [mobile, setMobile] = useState(false);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    api("/session")
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false));
  }, []);
  const toggleTheme = useCallback(() => {
    setDark((value) => {
      const next = !value;
      document.documentElement.classList.toggle("dark", next);
      localStorage.setItem("cesar-core-theme", next ? "dark" : "light");
      return next;
    });
  }, []);
  if (authenticated === null)
    return (
      <div className="grid min-h-screen place-items-center">
        <RefreshCw className="animate-spin text-blue-600" />
      </div>
    );
  if (!authenticated)
    return (
      <Login
        onLogin={() => setAuthenticated(true)}
        dark={dark}
        toggle={toggleTheme}
      />
    );
  const Current =
    {
      overview: Overview,
      applications: Applications,
      credentials: Credentials,
      usage: Usage,
      routes: Routes,
      health: Health,
    }[screen] ?? Overview;
  const navigate = (id: string) => {
    setScreen(id);
    location.hash = id;
    setMobile(false);
  };
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      {mobile && (
        <button
          className="fixed inset-0 z-20 bg-slate-950/50 lg:hidden"
          aria-label="Fechar menu"
          onClick={() => setMobile(false)}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-[270px] border-r border-slate-200 bg-white p-5 transition-transform dark:border-slate-800 dark:bg-slate-950 lg:sticky lg:top-0 lg:w-auto lg:translate-x-0 ${mobile ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-600 text-white">
              <ShieldCheck size={20} />
            </span>
            <div>
              <div className="font-bold">César Core</div>
              <div className="text-xs text-slate-500">Control Plane</div>
            </div>
          </div>
          <button className="lg:hidden" onClick={() => setMobile(false)}>
            <X />
          </button>
        </div>
        <nav className="space-y-1">
          {navigation.map(([id, label, Icon]) => (
            <button
              key={id}
              onClick={() => navigate(id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium ${screen === id ? "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"}`}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>
        <button
          className="absolute bottom-5 left-5 flex items-center gap-2 text-sm text-slate-500"
          onClick={async () => {
            await api("/logout", { method: "POST" });
            sessionStorage.clear();
            setAuthenticated(false);
          }}
        >
          <LogOut size={17} /> Sair
        </button>
      </aside>
      <main className="min-w-0">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90 sm:px-7">
          <button
            className="btn-secondary !p-2.5 lg:hidden"
            onClick={() => setMobile(true)}
          >
            <Menu size={18} />
          </button>
          <div className="hidden text-sm text-slate-500 sm:block">
            Ambiente administrativo seguro
          </div>
          <div className="flex items-center gap-2">
            <button
              className="btn-secondary !p-2.5"
              onClick={() => setNonce((n) => n + 1)}
              title="Atualizar"
            >
              <RefreshCw size={18} />
            </button>
            <ThemeToggle dark={dark} onChange={toggleTheme} />
          </div>
        </header>
        <div className="mx-auto max-w-[1440px] p-4 sm:p-7">
          <Current key={nonce} />
        </div>
      </main>
    </div>
  );
}

function Login({
  onLogin,
  dark,
  toggle,
}: {
  onLogin: () => void;
  dark: boolean;
  toggle: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden p-5">
      <div className="absolute right-5 top-5">
        <ThemeToggle dark={dark} onChange={toggle} />
      </div>
      <form
        className="panel relative w-full max-w-sm p-7"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const result = await api<{ csrf_token: string }>("/login", {
              method: "POST",
              body: JSON.stringify({ password }),
            });
            setCsrf(result.csrf_token);
            onLogin();
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="mb-7">
          <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-blue-600 text-white">
            <ShieldCheck />
          </span>
          <h1 className="text-2xl font-bold">César Core</h1>
          <p className="mt-1 text-sm text-slate-500">Acesso ao Control Plane</p>
        </div>
        <label className="label" htmlFor="admin-password">
          Senha do administrador
        </label>
        <input
          id="admin-password"
          className="input"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
        />
        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
        <button className="btn-primary mt-5 w-full" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
