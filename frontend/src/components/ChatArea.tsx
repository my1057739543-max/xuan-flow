"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Bot, TerminalSquare, ArrowUp, Activity, ChevronDown, XCircle, Plus, MessageSquare, Trash2, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type SessionInfo = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    return d.toLocaleDateString();
  } catch {
    return "";
  }
}

export function ChatArea() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [availableModels, setAvailableModels] = useState<{ name: string, display_name: string }[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Session state
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Broadcast typing status to Sidebar for adaptive polling
  useEffect(() => {
    const channel = new BroadcastChannel("typing_status");
    channel.postMessage({ isTyping });
    return () => channel.close();
  }, [isTyping]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Load sessions on mount
  useEffect(() => {
    fetchSessions();
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/management/available_models`);
      if (res.ok) {
        const data = await res.json();
        setAvailableModels(data.models || []);
        if (data.models && data.models.length > 0) {
          setSelectedModel(data.models[0].name);
        }
      }
    } catch (e) {
      console.error("Failed to fetch models", e);
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error("Failed to fetch sessions", e);
    }
  };

  const loadSession = async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        setCurrentSessionId(sessionId);
        setSessionDropdownOpen(false);
      }
    } catch (e) {
      console.error("Failed to load session", e);
    }
  };

  const newChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
    setSessionDropdownOpen(false);
  };

  const deleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        if (currentSessionId === sessionId) {
          setMessages([]);
          setCurrentSessionId(null);
        }
        await fetchSessions();
      }
    } catch (error) {
      console.error("Failed to delete session", error);
    }
  };

  const handleCancel = async () => {
    try {
      await fetch(`${API_BASE}/api/chat/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: currentSessionId || "default-thread" }),
      });
      setIsTyping(false);
    } catch (e) {
      console.error("Failed to cancel task", e);
      setIsTyping(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;

    const userMessage: Message = { role: "user", content: input.trim() };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: updatedMessages,
          thread_id: currentSessionId || undefined,
          model: selectedModel || undefined,
        }),
      });

      if (!response.ok) throw new Error("Network response was not ok");
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let aiContent = "";
      let hasStarted = false;
      let responseThreadId: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data:")) continue;

          const dataStr = trimmed.slice(5).trim();
          if (dataStr === "[DONE]") continue;

          try {
            const data = JSON.parse(dataStr);
            if (data.content) {
              aiContent += data.content;

              if (!hasStarted) {
                setMessages((prev) => [...prev, { role: "assistant", content: aiContent }]);
                hasStarted = true;
              } else {
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastMsg = newMessages[newMessages.length - 1];
                  if (lastMsg && lastMsg.role === "assistant") {
                    lastMsg.content = aiContent;
                  }
                  return newMessages;
                });
              }
            }
            if (data.thread_id) {
              responseThreadId = data.thread_id;
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
      }

      // After stream completes, update session tracking
      if (responseThreadId && !currentSessionId) {
        setCurrentSessionId(responseThreadId);
      }
      await fetchSessions();

    } catch (error) {
      console.error("Streaming error:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "Error communicating with context engine." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Derive current session title
  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const dropdownLabel = currentSession ? currentSession.title : "New Chat";

  return (
    <div className="flex flex-col h-full w-full relative bg-transparent">

      {/* Header Bar */}
      <div className="absolute top-0 w-full px-8 py-5 flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          {/* Session Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
              className="flex items-center gap-2 bg-white/10 border border-white/20 backdrop-blur-xl px-4 py-2 rounded-full shadow-[0_4px_30px_rgba(0,0,0,0.1)] hover:bg-white/20 transition-all min-w-[160px]"
            >
              <MessageSquare className="w-4 h-4 text-cyan-300 shrink-0 drop-shadow-[0_0_8px_rgba(103,232,249,0.8)]" />
              <span className="text-[13px] font-semibold text-white truncate drop-shadow-sm max-w-[180px]">
                {dropdownLabel}
              </span>
              <ChevronDown className={cn(
                "w-3.5 h-3.5 text-white/60 transition-transform shrink-0",
                sessionDropdownOpen && "rotate-180"
              )} />
            </button>

            <AnimatePresence>
              {sessionDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -8, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.95 }}
                  transition={{ duration: 0.15 }}
                  className="absolute top-full mt-2 left-0 w-[320px] max-h-[400px] overflow-y-auto bg-slate-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.5)] z-50 custom-scrollbar"
                >
                  {/* New Chat option */}
                  <button
                    onClick={newChat}
                    className={cn(
                      "w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/10 transition-colors border-b border-white/10",
                      !currentSessionId && "bg-cyan-500/10"
                    )}
                  >
                    <Plus className="w-4 h-4 text-cyan-400" />
                    <span className="text-[13px] font-semibold text-white">New Chat</span>
                  </button>

                  {/* Session list */}
                  {sessions.length === 0 ? (
                    <div className="px-4 py-6 text-center text-white/40 text-[12px]">
                      No saved conversations yet.
                    </div>
                  ) : (
                    sessions.map((session) => (
                      <div
                        key={session.id}
                        onClick={() => loadSession(session.id)}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/10 transition-colors group border-b border-white/5 last:border-b-0 cursor-pointer",
                          currentSessionId === session.id && "bg-cyan-500/10"
                        )}
                      >
                        {currentSessionId === session.id ? (
                          <Check className="w-4 h-4 text-cyan-400 shrink-0" />
                        ) : (
                          <MessageSquare className="w-4 h-4 text-white/30 shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] text-white/90 truncate font-medium">
                            {session.title}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-white/40">
                            <span>{session.message_count} messages</span>
                            <span>·</span>
                            <span>{formatTime(session.updated_at)}</span>
                          </div>
                        </div>
                        <button
                          onClick={(e) => deleteSession(e, session.id)}
                          className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-rose-500/20 text-rose-300 transition-all shrink-0"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {availableModels.length > 0 && (
            <div className="relative group">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="appearance-none bg-black/40 border border-white/10 backdrop-blur-xl text-white/90 text-[11px] font-bold py-2 px-4 pr-10 rounded-full focus:outline-none focus:border-cyan-500/50 transition-all cursor-pointer hover:bg-black/60 shadow-lg tracking-wide uppercase"
              >
                {availableModels.map(m => (
                  <option key={m.name} value={m.name} className="bg-slate-900 text-white">{m.display_name}</option>
                ))}
              </select>
              <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none opacity-50 group-hover:opacity-100 transition-opacity">
                <ChevronDown className="w-3 h-3 text-white" />
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 bg-black/20 border border-white/10 backdrop-blur-md px-3 py-1.5 rounded-full shadow-lg">
          <Activity className="w-4 h-4 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          <span className="text-[11px] font-bold text-white uppercase tracking-widest drop-shadow-sm">Ready</span>
        </div>
      </div>

      {/* Messages Canvas */}
      <div className="flex-1 overflow-y-auto w-full scroll-smooth px-4 sm:px-8 z-10 pt-24 pb-48 text-white">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, filter: "blur(10px)", scale: 0.95 }} animate={{ opacity: 1, filter: "blur(0px)", scale: 1 }} transition={{ duration: 1 }}
            className="h-full flex flex-col items-center justify-center text-white p-8 relative"
          >
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-cyan-500/20 rounded-full blur-[100px] pointer-events-none" />

            <div className="mb-8 p-6 rounded-3xl glass-panel relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-tr from-fuchsia-500/30 to-cyan-500/30 opacity-50 group-hover:opacity-100 transition-opacity duration-1000" />
              <Sparkles className="w-12 h-12 text-white relative z-10 drop-shadow-[0_0_15px_rgba(255,255,255,0.8)]" />
            </div>

            <h3 className="text-3xl font-bold tracking-tight text-white drop-shadow-[0_4px_20px_rgba(255,255,255,0.4)] text-center">Awaken the Engine.</h3>
            <p className="text-base mt-4 max-w-md text-center leading-relaxed text-white/70 font-medium drop-shadow-md">
              Xuan-Flow is fully integrated with your workspace. Cast a command into the aurora.
            </p>
          </motion.div>
        ) : (
          <div className="max-w-4xl mx-auto w-full flex flex-col gap-8 pb-10">
            <AnimatePresence initial={false}>
              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, type: "spring", stiffness: 200, damping: 20 }}
                  className={cn(
                    "flex flex-col gap-2 relative",
                    msg.role === "assistant" ? "items-start" : "items-end"
                  )}
                >
                  <span className={cn(
                    "text-[10px] uppercase tracking-widest font-bold px-3 drop-shadow-md",
                    msg.role === "assistant" ? "text-cyan-300" : "text-fuchsia-300"
                  )}>
                    {msg.role === "assistant" ? "Xuan-Flow" : "You"}
                  </span>

                  <div
                    className={cn(
                      "px-7 py-5 text-[15px] max-w-[85%] relative overflow-hidden",
                      msg.role === "assistant"
                        ? "glass-bubble-ai text-white rounded-[28px] rounded-tl-sm"
                        : "glass-bubble-user text-white rounded-[28px] rounded-tr-sm"
                    )}
                  >
                    {msg.role === "assistant" && (
                      <div className="absolute top-0 left-0 w-32 h-32 bg-cyan-400/20 rounded-full blur-2xl transform -translate-x-1/2 -translate-y-1/2 pointer-events-none" />
                    )}

                    <div className="relative z-10">
                      {msg.role === "assistant" ? (
                        <div className="prose prose-invert prose-p:leading-[1.8] prose-p:text-white/90 prose-pre:bg-black/40 prose-pre:backdrop-blur-xl prose-pre:border prose-pre:border-white/10 prose-pre:shadow-2xl max-w-none prose-headings:font-bold prose-headings:text-white prose-a:text-cyan-300 hover:prose-a:text-cyan-200 prose-code:text-cyan-200 prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-strong:text-white drop-shadow-sm">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="whitespace-pre-wrap leading-relaxed font-medium drop-shadow-md">{msg.content}</div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {isTyping && messages[messages.length - 1]?.role !== "assistant" && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-2 items-start">
                <span className="text-[10px] uppercase tracking-widest font-bold px-3 text-cyan-300 drop-shadow-md">Xuan-Flow</span>
                <div className="glass-bubble-ai border border-white/20 rounded-[28px] rounded-tl-sm px-6 py-5 flex gap-2 items-center shadow-lg">
                  <motion.span animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0 }} className="w-2 h-2 bg-white/80 rounded-full shadow-[0_0_8px_rgba(255,255,255,0.8)]" />
                  <motion.span animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.2 }} className="w-2 h-2 bg-white/80 rounded-full shadow-[0_0_8px_rgba(255,255,255,0.8)]" />
                  <motion.span animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }} transition={{ repeat: Infinity, duration: 1.5, delay: 0.4 }} className="w-2 h-2 bg-white/80 rounded-full shadow-[0_0_8px_rgba(255,255,255,0.8)]" />
                </div>
              </motion.div>
            )}
            <div ref={bottomRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Floating Command Bar */}
      <div className="absolute bottom-8 left-0 w-full px-6 flex justify-center z-30 pointer-events-none">
        <div className="w-full max-w-3xl pointer-events-auto">
          <div className="relative group rounded-[32px] overflow-visible">
            {/* Extremely intense backdrop blur container for input */}
            <div className="relative bg-white/5 backdrop-blur-[40px] rounded-[32px] border border-white/20 flex items-end px-3 py-3 transition-all focus-within:bg-white/10 focus-within:border-white/40 focus-within:shadow-[0_10px_50px_rgba(255,255,255,0.1)]">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Cast a spell into the void..."
                className="flex-1 bg-transparent border-none resize-none px-5 py-3 text-[16px] text-white placeholder:text-white/50 focus:outline-none min-h-[50px] max-h-[200px] leading-relaxed font-medium drop-shadow-sm"
                rows={1}
                disabled={isTyping}
              />
              {isTyping ? (
                <button
                  onClick={handleCancel}
                  className="mb-1.5 mr-1.5 p-3.5 bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-2xl hover:bg-rose-500/30 transition-all shadow-lg flex items-center justify-center hover:scale-105 active:scale-95 group"
                >
                  <XCircle size={20} strokeWidth={3} className="group-hover:text-rose-300" />
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  disabled={!input.trim()}
                  className="mb-1.5 mr-1.5 p-3.5 bg-white text-black rounded-2xl hover:bg-white/90 disabled:opacity-30 disabled:hover:bg-white transition-all shadow-[0_4px_15px_rgba(255,255,255,0.3)] flex items-center justify-center disabled:cursor-not-allowed hover:scale-105 active:scale-95"
                >
                  <ArrowUp size={20} strokeWidth={3} />
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center justify-center gap-5 mt-4 opacity-70">
            <span className="text-[11px] text-white/70 font-semibold tracking-wider uppercase">Press <kbd className="font-sans px-1.5 py-0.5 rounded-md border border-white/20 mx-1 bg-black/20">Enter</kbd> to execute</span>
            <span className="text-[11px] text-white/70 font-semibold tracking-wider uppercase">Press <kbd className="font-sans px-1.5 py-0.5 rounded-md border border-white/20 mx-1 bg-black/20">Shift + Enter</kbd> to break line</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Sparkles local declaration
function Sparkles(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
    </svg>
  );
}
