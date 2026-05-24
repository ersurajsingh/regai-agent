"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { sendQuery, createSession } from "@/lib/api";

interface Message {
  role: "user" | "agent";
  content: string;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    createSession().then((s) => setSessionId(s.session_id));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const data = await sendQuery(sessionId, input);
      setMessages((prev) => [...prev, { role: "agent", content: data.answer }]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl flex flex-col gap-4">
      <div className="bg-gray-900 rounded-xl p-4 h-[60vh] overflow-y-auto flex flex-col gap-3">
        {messages.length === 0 && (
          <p className="text-gray-500 text-sm text-center mt-8">
            Ask a compliance question to get started.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`rounded-lg px-4 py-2 max-w-[85%] text-sm ${
              msg.role === "user"
                ? "bg-indigo-600 self-end"
                : "bg-gray-800 self-start"
            }`}
          >
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        ))}
        {loading && (
          <div className="bg-gray-800 self-start rounded-lg px-4 py-2 text-sm text-gray-400 animate-pulse">
            Thinking...
          </div>
        )}
        {error && (
          <div className="bg-red-900/50 text-red-300 rounded-lg px-4 py-2 text-sm self-start">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a compliance question..."
          className="flex-1 bg-gray-800 rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
          disabled={loading}
          maxLength={4000}
          aria-label="Compliance query input"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          aria-label="Send query"
        >
          Send
        </button>
      </form>
    </div>
  );
}
