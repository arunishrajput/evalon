"use client";

import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ModelLoadingState } from "@/components/states/ModelLoadingState";
import { chatApi } from "@/lib/api";
import { sendChatMessage } from "@/lib/chat";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

const SUGGESTED_QUESTIONS = [
  "Why did I get this score?",
  "What's the single highest-impact improvement I could make?",
  "Why am I ranked where I am, and not higher?",
  "What did teams above me do differently?",
];

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export function ChatInterface({ submissionId }: { submissionId: string }) {
  const token = useAuthStore((s) => s.accessToken);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [queuedNotice, setQueuedNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatApi.history(submissionId).then((history: ChatMessage[]) => {
      setMessages(history.map((m) => ({ id: m.id, role: m.role, content: m.content })));
    });
  }, [submissionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (content: string) => {
    if (!content.trim() || sending) return;
    setErrorNotice(null);
    setQueuedNotice(null);
    setInput("");
    const userMessage: DisplayMessage = { id: `local-${Date.now()}`, role: "user", content };
    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [...prev, userMessage, { id: assistantId, role: "assistant", content: "", streaming: true }]);
    setSending(true);

    await sendChatMessage(submissionId, content, token, {
      onToken: (token) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m))
        );
      },
      onDone: (_id, error) => {
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)));
        if (error) setErrorNotice(error);
        setSending(false);
      },
      onQueued: (retryAfter, message) => {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        setQueuedNotice(message);
        setSending(false);
        setTimeout(() => setQueuedNotice(null), retryAfter * 1000);
      },
      onError: (message) => {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        setErrorNotice(message);
        setSending(false);
      },
    });
  };

  return (
    <div className="flex h-[600px] flex-col rounded-lg border border-white/10 bg-card">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div>
            <p className="mb-3 text-sm text-gray-500">Ask your mentor anything about your evaluation.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-gray-400 hover:border-accent/40 hover:text-white"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[85%] whitespace-pre-wrap rounded-lg px-4 py-2 text-sm",
                m.role === "user" ? "bg-accent text-white" : "bg-card-elevated text-gray-100"
              )}
            >
              {m.content || (m.streaming ? <TypingDots /> : "")}
            </div>
          </div>
        ))}
      </div>

      {queuedNotice && (
        <div className="border-t border-white/10 p-3">
          <ModelLoadingState message={queuedNotice} />
        </div>
      )}
      {errorNotice && <p className="border-t border-white/10 px-4 py-2 text-xs text-error">{errorNotice}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-end gap-2 border-t border-white/10 p-3"
      >
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder="Ask your mentor a question..."
          rows={2}
          className="flex-1 resize-none"
          disabled={sending}
        />
        <Button type="submit" size="icon" disabled={sending || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="flex gap-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-500" />
    </span>
  );
}
