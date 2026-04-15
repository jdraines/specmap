class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  timeout: number = 30_000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(path, {
      credentials: 'include',
      ...init,
      signal: controller.signal,
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
  } finally {
    clearTimeout(timer);
  }
}
