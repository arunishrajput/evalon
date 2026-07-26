import { chatApi } from "./api";
import type { ChatTokenEvent } from "./types";

interface SendMessageHandlers {
  onToken: (token: string) => void;
  onDone: (messageId: string, error?: string) => void;
  onQueued: (retryAfter: number, message: string) => void;
  onError: (message: string) => void;
}

/** POST .../messages IS the SSE stream (spec Section 9) — but it can also
 * resolve as a one-shot HTTP 202 JSON body when the P3 inference lock times
 * out, so this can't reuse the plain GET-only streamSSE helper. */
export async function sendChatMessage(
  submissionId: string,
  content: string,
  token: string | null,
  handlers: SendMessageHandlers
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(chatApi.messagesUrl(submissionId), {
      method: "POST",
      headers,
      body: JSON.stringify({ content }),
    });
  } catch {
    handlers.onError("Couldn't reach the mentor. Check your connection and try again.");
    return;
  }

  if (res.status === 202) {
    const body = await res.json().catch(() => ({ retry_after: 30, message: "The mentor is busy. Please try again shortly." }));
    handlers.onQueued(body.retry_after ?? 30, body.message ?? "The mentor is busy. Please try again shortly.");
    return;
  }

  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    handlers.onError(body.detail || "Something went wrong reaching the mentor. Please try again.");
    return;
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
      if (!dataLine) continue;
      try {
        const event = JSON.parse(dataLine.slice("data: ".length)) as ChatTokenEvent;
        if (event.done) {
          handlers.onDone(event.message_id || "", event.error);
        } else {
          handlers.onToken(event.token);
        }
      } catch {
        // ignore malformed frames
      }
    }
  }
}
