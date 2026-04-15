class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    credentials: 'include',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (resp.status === 401) {
    // Redirect to app root — the app router shows login/setup based on auth status
    window.location.href = '/';
    throw new ApiError(401, 'Unauthorized');
  }

  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body);
  }

  return resp.json() as Promise<T>;
}
