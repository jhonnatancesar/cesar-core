let csrf = sessionStorage.getItem("cesar-core-csrf") ?? "";

export function setCsrf(value: string) {
  csrf = value;
  sessionStorage.setItem("cesar-core-csrf", value);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET") headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`/admin/api${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const detail = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new Error(detail.detail ?? "Request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
