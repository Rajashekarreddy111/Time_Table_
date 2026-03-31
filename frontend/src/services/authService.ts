export type AuthUser = {
  id: string;
  username: string;
  role: "admin" | "coordinator";
};

type LoginRole = "admin" | "coordinator";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

async function authRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
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
  const data = await authRequest<{ user: AuthUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password, role }),
  });
  return data.user;
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    return await authRequest<AuthUser>("/auth/me", { method: "GET" });
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await authRequest("/auth/logout", { method: "POST" });
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
