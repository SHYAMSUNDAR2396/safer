export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
  csrf?: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "Cannot reach the portal. Your entered values have been kept. Try again.",
    );
  }
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    const fields = problem.field_errors
      ?.map(
        (f: { field: string; message: string }) =>
          `${f.field ? f.field + ": " : ""}${f.message}`,
      )
      .join(" · ");
    throw new ApiError(
      response.status,
      fields ||
        problem.detail ||
        `Request failed (${response.status}). Please try again.`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export function money(value: string): string {
  // Preserve decimal precision when formatting NUMERIC(18,2); never round through Number.
  const [whole, fraction = "00"] = value.split(".");
  return `₹${BigInt(whole).toLocaleString("en-IN")}.${fraction.padEnd(2, "0")}`;
}
export function day(value: string): string {
  return new Date(value + "T12:00:00").toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
