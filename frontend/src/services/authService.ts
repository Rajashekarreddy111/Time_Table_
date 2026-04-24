export type AuthUser = {
  id: string;
  username: string;
  role: "admin" | "coordinator";
};

const SESSION_STORAGE_KEY = "tt_session_id";
const SESSION_HEADER_NAME = "X-Session-Id";

type LoginRole = "admin" | "coordinator";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

function getSessionId(): string | null {
  return window.localStorage.getItem(SESSION_STORAGE_KEY);
}

function setSessionId(sessionId: string | null) {
  if (sessionId) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    return;
  }
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

function buildAuthHeaders(headers?: HeadersInit): HeadersInit {
  const sessionId = getSessionId();
  return {
    ...(headers ?? {}),
    ...(sessionId ? { "X-Session-Id": sessionId } : {}),
  };
}

async function authRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(options.headers),
    },
    ...options,
  });

  if (!response.ok) {
    if (response.status === 401) {
      setSessionId(null);
    }
    let message = `Request failed (${response.status})`;
    try {
      const errorData = await response.json();
      message =
        errorData.message ||
        errorData.detail?.message ||
        errorData.detail ||
        message;
    } catch {
      // ignore json parse issues
    }
    throw new Error(message);
  }

  const rotatedSessionId = response.headers.get(SESSION_HEADER_NAME);
  if (rotatedSessionId) {
    setSessionId(rotatedSessionId);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function login(
  username: string,
  password: string,
  role: LoginRole,
): Promise<AuthUser> {
  const data = await authRequest<{ user: AuthUser; sessionId: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password, role }),
  });
  setSessionId(data.sessionId);
  return data.user;
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    return await authRequest<AuthUser>("/auth/me", { method: "GET" });
  } catch {
    setSessionId(null);
    return null;
  }
}

export async function logout(): Promise<void> {
  try {
    await authRequest("/auth/logout", { method: "POST" });
  } finally {
    setSessionId(null);
  }
}

export async function changeAdminPassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await authRequest("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ currentPassword, newPassword }),
  });
}

export async function changeAdminUsername(
  currentPassword: string,
  newUsername: string,
): Promise<AuthUser> {
  return authRequest<AuthUser>("/auth/change-username", {
    method: "POST",
    body: JSON.stringify({ currentPassword, newUsername }),
  });
}

export async function listCoordinators(): Promise<AuthUser[]> {
  const data = await authRequest<{ items: AuthUser[] }>(
    "/auth/coordinators",
    { method: "GET" },
  );
  return data.items;
}

export async function createCoordinator(
  username: string,
  password: string,
): Promise<AuthUser> {
  return authRequest<AuthUser>("/auth/coordinators", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function updateCoordinatorPassword(
  username: string,
  newPassword: string,
): Promise<void> {
  await authRequest(`/auth/coordinators/${encodeURIComponent(username)}/password`, {
    method: "PUT",
    body: JSON.stringify({ newPassword }),
  });
}

export async function deleteCoordinator(username: string): Promise<void> {
  await authRequest(`/auth/coordinators/${encodeURIComponent(username)}`, {
    method: "DELETE",
  });
}

export function getStoredSessionId(): string | null {
  return getSessionId();
}
