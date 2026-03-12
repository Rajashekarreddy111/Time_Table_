export type AuthUser = {
  id: string;
  name: string;
  role?: string;
};

export async function login(_username: string, _password: string): Promise<AuthUser | null> {
  return null;
}

export async function logout(): Promise<void> {
  return;
}
