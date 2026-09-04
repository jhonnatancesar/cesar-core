import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

test("renders login and persists light/dark preference", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({ ok: false, json: async () => ({ detail: "no" }) }),
  );
  render(<App />);
  await screen.findByText("Acesso ao Control Plane");
  fireEvent.click(screen.getByLabelText(/Usar tema/));
  expect(localStorage.getItem("cesar-core-theme")).toMatch(/light|dark/);
});

test("logs in with a password and shows the six-screen shell", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "no" }) })
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ authenticated: true, csrf_token: "csrf" }),
    })
    .mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        version: "1.1.0",
        uptime_seconds: 60,
        applications: 2,
        active_applications: 1,
        credentials: 1,
        ai_requests_24h: 0,
        search_requests_24h: 0,
        errors_24h: 0,
        readiness: { status: "ok" },
        dependencies: [],
      }),
    });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  await screen.findByText("Acesso ao Control Plane");
  fireEvent.change(screen.getByLabelText("Senha do administrador"), {
    target: { value: "secret" },
  });
  fireEvent.click(screen.getByText("Entrar"));
  await waitFor(() =>
    expect(screen.getByText("Visão geral")).toBeInTheDocument(),
  );
  expect(screen.getAllByText("Aplicações").length).toBeGreaterThan(0);
  expect(screen.getByText("Chaves de API")).toBeInTheDocument();
  expect(screen.getByText("Uso & quotas")).toBeInTheDocument();
  expect(screen.getByText("Rotas")).toBeInTheDocument();
  expect(screen.getByText("Saúde")).toBeInTheDocument();
});
