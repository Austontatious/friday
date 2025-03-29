import React, { useState } from "react";
import "./App.css";

// ChatInput Component
function ChatInput({ onSend }: { onSend: (message: string) => void }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="w-full flex mt-4">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask FRIDAY something..."
        className="flex-grow px-4 py-2 rounded-l-lg border border-cyan-500 bg-black text-cyan-300 focus:outline-none"
      />
      <button
        type="submit"
        className="px-4 py-2 bg-cyan-500 text-black font-bold rounded-r-lg hover:bg-cyan-400 transition"
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

  // Dynamically determine backend URL
  const BACKEND_URL = `${window.location.origin.replace(/:\d+$/, "")}:8001/process`;

  const handleTask = async (task: string) => {
    setLoading(true);
    setResponse("Processing...");

    try {
      const res = await fetch(`${BACKEND_URL}/${task}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });

      const data = await res.json();
      setResponse(data.response);
    } catch (err) {
      setResponse("Error communicating with FRIDAY.");
    }

    setLoading(false);
  };

  const handleSend = async (message: string) => {
    setLoading(true);
    setResponse("Thinking...");

    try {
      const res = await fetch(`${BACKEND_URL}/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: message }),
      });

      const data = await res.json();
      setResponse(data.response);
    } catch (err) {
      setResponse("FRIDAY encountered an error.");
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-black text-cyan-400 font-mono flex flex-col items-center justify-start p-4">
      <h1 className="text-4xl mb-4 text-cyan-300 drop-shadow-glow">FRIDAY</h1>

      <ChatInput onSend={handleSend} />

      <textarea
        placeholder="Paste your code here..."
        className="w-full max-w-2xl h-48 p-3 bg-zinc-900 text-cyan-300 rounded-xl border border-cyan-700 mb-4 shadow-inner"
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />

      <div className="flex gap-4 mb-6">
        <button
          onClick={() => handleTask("explain")}
          className="bg-blue-700 hover:bg-blue-500 px-4 py-2 rounded-lg shadow-glow"
        >
          Explain
        </button>
        <button
          onClick={() => handleTask("fix_bugs")}
          className="bg-yellow-600 hover:bg-yellow-400 px-4 py-2 rounded-lg shadow-glow"
        >
          Fix Bugs
        </button>
        <button
          onClick={() => handleTask("generate_tests")}
          className="bg-green-700 hover:bg-green-500 px-4 py-2 rounded-lg shadow-glow"
        >
          Write Tests
        </button>
      </div>

      <div className="w-full max-w-2xl bg-zinc-800 text-cyan-200 rounded-xl p-4 border border-cyan-700 shadow-inner whitespace-pre-wrap">
        {loading ? "Running task..." : response}
      </div>
    </div>
  );
}

export default App;
