// The browser's native EventSource can't send an Authorization header, and
// every EVALON SSE endpoint requires a Bearer token — so streams are read
// via fetch()'s ReadableStream instead, parsing the `data: ...\n\n` frames
// by hand. Lines without a `data:` prefix (SSE comments, i.e. keepalives)
// are silently skipped.

export async function streamSSE(
  url: string,
  token: string | null,
  onEvent: (raw: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { headers, signal });
  if (!res.ok || !res.body) {
    throw new Error(`Stream connection failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
      if (dataLine) onEvent(dataLine.slice("data: ".length));
    }
  }
}
