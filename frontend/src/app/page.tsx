import ChatInterface from "@/components/ChatInterface";

export default function Home() {
  return (
    <main className="flex flex-col items-center justify-center min-h-screen p-4">
      <div className="flex items-center justify-between w-full max-w-2xl mb-6">
        <h1 className="text-2xl font-bold text-indigo-400">RegAI Compliance Agent</h1>
        <a
          href="/observe"
          className="text-xs text-gray-500 hover:text-indigo-400 transition-colors border border-gray-800 hover:border-indigo-500/40 px-3 py-1.5 rounded-lg"
        >
          Observability →
        </a>
      </div>
      <ChatInterface />
    </main>
  );
}
