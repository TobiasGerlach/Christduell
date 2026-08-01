import { ApiError, api, setAccessToken, setUnauthorizedHandler } from "../api/client";

function mockFetch(response: Partial<Response> & { status: number }) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: response.status < 400,
    status: response.status,
    statusText: "",
    text: async () => (response as { body?: string }).body ?? "",
    json: async () => JSON.parse((response as { body?: string }).body ?? "{}"),
  });
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

afterEach(() => {
  setAccessToken(null);
  setUnauthorizedHandler(null);
  jest.restoreAllMocks();
});

describe("api client", () => {
  it("sends no Authorization header while logged out", async () => {
    const fetchMock = mockFetch({ status: 200, body: "{}" } as never);

    await api.get("/duels");

    const headers = fetchMock.mock.calls[0][1].headers;
    expect(headers.Authorization).toBeUndefined();
  });

  it("attaches the bearer token once one is set", async () => {
    const fetchMock = mockFetch({ status: 200, body: "{}" } as never);
    setAccessToken("token-123");

    await api.get("/duels");

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer token-123");
  });

  it("surfaces the server's detail message instead of raw JSON", async () => {
    mockFetch({ status: 409, body: '{"detail":"Du hast bereits ein aktives Abo"}' } as never);

    await expect(api.post("/billing/checkout")).rejects.toThrow("Du hast bereits ein aktives Abo");
  });

  it("joins the messages of a validation error", async () => {
    mockFetch({
      status: 422,
      body: '{"detail":[{"msg":"zu kurz"},{"msg":"ungültig"}]}',
    } as never);

    await expect(api.post("/auth/register", {})).rejects.toThrow("zu kurz, ungültig");
  });

  it("reports the status code on the error", async () => {
    mockFetch({ status: 404, body: '{"detail":"Spieler nicht gefunden"}' } as never);

    await expect(api.get("/players/9")).rejects.toMatchObject({ status: 404 } as ApiError);
  });

  it("notifies the app when the session is rejected", async () => {
    mockFetch({ status: 401, body: '{"detail":"Not authenticated"}' } as never);
    const onUnauthorized = jest.fn();
    setUnauthorizedHandler(onUnauthorized);

    await expect(api.get("/auth/me")).rejects.toThrow();

    // The whole app drops to the login screen from this one callback.
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("returns undefined for 204 responses", async () => {
    mockFetch({ status: 204, body: "" } as never);

    await expect(api.delete("/research/consent")).resolves.toBeUndefined();
  });
});
