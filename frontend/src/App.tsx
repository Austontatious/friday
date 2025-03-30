import React, { useState, useEffect } from "react";
import { TaskManager } from "./components/TaskManager";
import { apiService } from "./services/api";
import { TaskResponse } from "./types";
import "./App.css";

// ChatInput Component
function ChatInput({ onSend, disabled }: { onSend: (message: string) => void; disabled: boolean }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto flex mt-4">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask FRIDAY something..."
        disabled={disabled}
        className="flex-grow px-4 py-2 rounded-l-lg border border-cyan-500 bg-black text-cyan-300 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        type="submit"
        disabled={disabled}
        className="px-4 py-2 bg-cyan-500 text-black font-bold rounded-r-lg hover:bg-cyan-400 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </form>
  );
}

// Main App Component
function App() {
  const [code, setCode] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const initializeApi = async () => {
      try {
        await apiService.getModelCapabilities();
        setIsInitialized(true);
      } catch (err) {
        setError("Failed to connect to FRIDAY. Please make sure the backend server is running.");
        console.error('API initialization error:', err);
      }
    };

    initializeApi();
  }, []);

  const handleTaskComplete = (taskResponse: TaskResponse) => {
    setResponse(taskResponse.response);
    setError(null);
  };

  const handleError = (errorMessage: string) => {
    setError(errorMessage);
    setResponse("");
  };

  const handleSend = async (message: string) => {
    if (!isInitialized) {
      setError("FRIDAY is still initializing. Please wait a moment.");
      return;
    }

    setLoading(true);
    setError(null);
    setResponse("Thinking...");

    try {
      const result = await apiService.processInput(message);
      setResponse(result.response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "FRIDAY encountered an error.");
      setResponse("");
    } finally {
      setLoading(false);
    }
  };

  if (!isInitialized) {
    return (
      <div className="min-h-screen bg-black text-cyan-400 font-mono flex flex-col items-center justify-center p-4">
        <h1 className="text-4xl mb-4 text-cyan-300 drop-shadow-glow">FRIDAY</h1>
        <div className="text-xl animate-pulse">Initializing...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-cyan-400 font-mono flex flex-col items-center justify-start p-4">
      <h1 className="text-4xl mb-4 text-cyan-300 drop-shadow-glow">FRIDAY</h1>

      <ChatInput onSend={handleSend} disabled={loading} />

      <textarea
        placeholder="Paste your code here..."
        className="w-full max-w-2xl h-48 p-3 bg-zinc-900 text-cyan-300 rounded-xl border border-cyan-700 mb-4 shadow-inner mt-4"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        disabled={loading}
      />

      <TaskManager 
        onTaskComplete={handleTaskComplete} 
        onError={handleError}
        code={code}
      />

      {error && (
        <div className="w-full max-w-2xl mt-4 p-4 bg-red-900/30 text-red-300 rounded-xl border border-red-700">
          {error}
        </div>
      )}

      {response && (
        <div className="w-full max-w-2xl mt-4 bg-zinc-800 text-cyan-200 rounded-xl p-4 border border-cyan-700 shadow-inner whitespace-pre-wrap">
          {loading ? "Running task..." : response}
        </div>
      )}
    </div>
  );
}

export default App;
