import Constants from "expo-constants";

// EXPO_PUBLIC_* variables are inlined at build time, which is how a production
// build points at the deployed API without editing app.json.
const API_BASE_URL: string =
  process.env.EXPO_PUBLIC_API_URL ??
  Constants.expoConfig?.extra?.apiBaseUrl ??
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let accessToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** Called when the server rejects our token, so the app can drop to the login screen. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

/** Turns FastAPI's error bodies into something worth showing a user. */
function messageFromBody(body: string, fallback: string): string {
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail;
    if (typeof detail === "string") return detail;
    // 422 validation errors arrive as a list of {loc, msg, ...}.
    if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) {
      return detail.map((item: { msg: string }) => item.msg).join(", ");
    }
  } catch {
    // Not JSON — fall through to the raw text.
  }
  return body || fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    const body = await response.text();
    if (response.status === 401) {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, messageFromBody(body, response.statusText));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
