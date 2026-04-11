"use client";

import { useEffect, useState } from "react";
import { Wrench, BrainCircuit, Library, Loader2, ChevronDown, FolderCode, FileText, CheckCircle2, RotateCw, Sparkles, Trash2, Activity, Timer } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { FilePreview } from "./FilePreview";
import { cn } from "@/lib/utils";

type Skill = { name: string; description: string; category: string; enabled: boolean };
type Tool = { name: string; description: string };
type MemoryFact = { content: string; category: string; confidence: number };
type WorkingMemory = { content: string };
type WorkspaceFile = { name: string; size: number; modified_at: number };
type Task = { content: string; status: "pending" | "in_progress" | "completed" };
type TraceEntry = { node: string; duration: number; timestamp: number; tools?: string[] };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function Sidebar() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [memory, setMemory] = useState<MemoryFact[]>([]);
  const [workingMemory, setWorkingMemory] = useState<string>("");
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [performance, setPerformance] = useState<TraceEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [openSkills, setOpenSkills] = useState(true);
  const [openTools, setOpenTools] = useState(true);
  const [openMemory, setOpenMemory] = useState(true);
  const [openWorkspace, setOpenWorkspace] = useState(true);
  const [openTasks, setOpenTasks] = useState(true);
  const [openPerformance, setOpenPerformance] = useState(false);
  const [previewFile, setPreviewFile] = useState<{ name: string; content: string } | null>(null);
  const [clearingAtomic, setClearingAtomic] = useState(false);
  const [clearingWorking, setClearingWorking] = useState(false);

  const fetchAllData = async () => {
    try {
      const [skillsRes, toolsRes, memoryRes, workingMemoryRes, workspaceRes, tasksRes, perfRes] = await Promise.all([
        fetch(`${API_BASE}/api/management/skills`),
        fetch(`${API_BASE}/api/management/tools`),
        fetch(`${API_BASE}/api/management/memory`),
        fetch(`${API_BASE}/api/management/working-memory`),
        fetch(`${API_BASE}/api/workspace/files`),
        fetch(`${API_BASE}/api/management/tasks`),
        fetch(`${API_BASE}/api/management/performance`),
      ]);

      if (skillsRes.ok) setSkills((await skillsRes.json()).skills || []);
      if (toolsRes.ok) setTools((await toolsRes.json()).tools || []);
      if (memoryRes.ok) setMemory((await memoryRes.json()).memory?.facts || []);
      if (workingMemoryRes.ok) setWorkingMemory((await workingMemoryRes.json()).working_memory || "");
      if (workspaceRes.ok) setWorkspaceFiles((await workspaceRes.json()).files || []);
      if (tasksRes.ok) setTasks((await tasksRes.json()).tasks || []);
      if (perfRes.ok) setPerformance((await perfRes.json()).performance || []);
    } catch (error) {
      console.error("Failed to fetch sidebar data", error);
    } finally {
      setLoading(false);
    }
  };

  const openFilePreview = async (filename: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/workspace/files/${encodeURIComponent(filename)}`);
      if (res.ok) {
        const data = await res.json();
        setPreviewFile({ name: filename, content: data.content });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const deleteWorkspaceFile = async (e: React.MouseEvent, filename: string) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/workspace/files/${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchAllData();
      }
    } catch (error) {
      console.error("Failed to delete workspace file", error);
    }
  };

  const clearAtomicMemory = async () => {
    if (clearingAtomic) return;
    if (!window.confirm("Clear all atomic memory facts (JSON)? This will not clear MySQL.")) return;
    setClearingAtomic(true);
    try {
      const res = await fetch(`${API_BASE}/api/management/memory/clear-atomic`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to clear atomic memory");
      await fetchAllData();
    } catch (error) {
      console.error("Failed to clear atomic memory", error);
      window.alert("Failed to clear atomic memory.");
    } finally {
      setClearingAtomic(false);
    }
  };

  const clearWorkingMemory = async () => {
    if (clearingWorking) return;
    if (!window.confirm("Clear working memory markdown (memory.md)? This will not clear MySQL.")) return;
    setClearingWorking(true);
    try {
      const res = await fetch(`${API_BASE}/api/management/memory/clear-working`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to clear working memory");
      await fetchAllData();
    } catch (error) {
      console.error("Failed to clear working memory", error);
      window.alert("Failed to clear working memory markdown.");
    } finally {
      setClearingWorking(false);
    }
  };

  useEffect(() => {
    fetchAllData();

    let intervalId: any;
    const startPolling = (ms: number) => {
      if (intervalId) clearInterval(intervalId);
      intervalId = setInterval(fetchAllData, ms);
    };

    // Initial state: idle polling
    startPolling(15000);

    // Dynamic polling based on Agent activity
    const channel = new BroadcastChannel("typing_status");
    channel.onmessage = (event) => {
      if (event.data.isTyping) {
        startPolling(2000); // Fast update when Agent is thinking
      } else {
        setTimeout(() => startPolling(15000), 1000); // Back to idle after a small delay
      }
    };

    return () => {
      clearInterval(intervalId);
      channel.close();
    };
  }, []);

  const SectionHeader = ({ title, icon, isOpen, toggle, count }: any) => (
    <button
      onClick={toggle}
      className="flex items-center justify-between w-full group py-2 px-1 text-white/70 hover:text-white transition-colors"
    >
      <div className="flex items-center gap-2.5">
        <div className="p-1 rounded bg-white/5 border border-white/10">{icon}</div>
        <span className="text-[12px] font-semibold tracking-wide">{title}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium bg-black/20 text-white/80 px-1.5 py-0.5 rounded-full border border-white/5">{count}</span>
        <motion.div animate={{ rotate: isOpen ? 0 : -90 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-4 h-4 opacity-50 group-hover:opacity-100 transition-opacity drop-shadow-md" />
        </motion.div>
      </div>
    </button>
  );

  return (
    <div className="w-[320px] h-full flex flex-col bg-transparent z-0 text-white">
      {/* Brand Header */}
      <div className="px-6 py-6 flex items-start justify-between border-b border-white/10 bg-black/10 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-fuchsia-500 to-cyan-500 flex items-center justify-center shadow-[0_0_20px_rgba(236,72,153,0.5)]">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <h1 className="text-lg font-bold tracking-tight text-white drop-shadow-[0_2px_10px_rgba(255,255,255,0.3)]">
              Xuan-Flow
            </h1>
          </div>
          <p className="text-white/60 text-[11px] font-medium tracking-wide">Autonomous Engine</p>
        </div>
        <button
          onClick={fetchAllData}
          disabled={loading}
          className="p-1.5 mt-1 text-white/50 hover:text-white hover:bg-white/10 rounded-xl transition-all disabled:opacity-50"
          title="Sync Data"
        >
          <RotateCw className={`w-4 h-4 drop-shadow-md ${loading ? 'animate-spin text-fuchsia-400' : ''}`} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 pb-8 pt-4 space-y-6 custom-scrollbar">
        {loading && tools.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[50vh] text-white/50 space-y-3">
            <Loader2 className="w-6 h-6 animate-spin text-fuchsia-400" />
            <span className="text-xs font-medium tracking-widest uppercase">Initializing Canvas</span>
          </div>
        ) : (
          <>
            {/* EXECUTION PLAN */}
            <div>
              <SectionHeader
                title="Execution Plan"
                icon={<BrainCircuit className="w-3.5 h-3.5 text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]" />}
                isOpen={openTasks}
                toggle={() => setOpenTasks(!openTasks)}
                count={tasks.length}
              />
              <AnimatePresence>
                {openTasks && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-2 pb-3 space-y-1.5">
                      {tasks.length === 0 ? (
                        <div className="text-white/40 text-[11px] italic px-2">No active objectives.</div>
                      ) : (
                        tasks.map((t, i) => (
                          <div key={i} className={cn(
                            "group flex items-start gap-2.5 py-1.5 px-2 rounded-xl border border-transparent transition-all",
                            t.status === "in_progress" ? "bg-cyan-500/10 border-cyan-500/20" : "hover:bg-white/5"
                          )}>
                            <div className="mt-1 flex-shrink-0">
                              {t.status === "completed" ? (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              ) : t.status === "in_progress" ? (
                                <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                              ) : (
                                <div className="w-3 h-3 rounded-full border border-white/20" />
                              )}
                            </div>
                            <span className={cn(
                              "text-[12px] leading-tight transition-colors",
                              t.status === "completed" ? "text-white/40 line-through" :
                                t.status === "in_progress" ? "text-cyan-200 font-medium" : "text-white/70"
                            )}>
                              {t.content}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            {/* EXECUTION TIMELINE (Performance Monitor) */}
            <div>
              <SectionHeader
                title="Execution Timeline"
                icon={<Timer className="w-3.5 h-3.5 text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.8)]" />}
                isOpen={openPerformance}
                toggle={() => setOpenPerformance(!openPerformance)}
                count={performance.length}
              />
              <AnimatePresence>
                {openPerformance && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-2 pb-4 space-y-3">
                      {performance.length === 0 ? (
                        <div className="text-white/40 text-[11px] italic px-2">No trace data available.</div>
                      ) : (
                        <>
                          <div className="flex flex-col gap-2.5">
                            {performance.map((entry, i) => (
                              <div key={i} className="relative pl-6">
                                {i < performance.length - 1 && (
                                  <div className="absolute left-2.5 top-4 bottom-[-10px] w-[1px] bg-white/10" />
                                )}
                                <div className="absolute left-1.5 top-1.5 w-2 h-2 rounded-full bg-white/20 border border-white/10" />

                                <div className="flex flex-col gap-1">
                                  <div className="flex items-center justify-between text-[11px]">
                                    <span className={cn(
                                      "font-semibold uppercase tracking-wider",
                                      entry.node === "agent" ? "text-fuchsia-400" : "text-cyan-400"
                                    )}>
                                      {entry.node === "agent" ? "Thinking" : "Executing"}
                                    </span>
                                    <span className="text-white/40 font-mono">{entry.duration.toFixed(2)}s</span>
                                  </div>

                                  <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                                    <motion.div
                                      initial={{ width: 0 }}
                                      animate={{ width: `${Math.min((entry.duration / 10) * 100, 100)}%` }}
                                      className={cn(
                                        "h-full rounded-full",
                                        entry.node === "agent" ? "bg-fuchsia-500/50" : "bg-cyan-500/50"
                                      )}
                                    />
                                  </div>

                                  {entry.tools && entry.tools.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-0.5">
                                      {entry.tools.map(t => (
                                        <span key={t} className="text-[9px] px-1.5 py-0.5 bg-cyan-500/5 text-cyan-300/60 rounded border border-cyan-500/10">
                                          {t}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between px-2">
                            <span className="text-[10px] text-white/40 uppercase tracking-widest font-semibold">Total Time</span>
                            <span className="text-sm font-bold text-amber-400 font-mono drop-shadow-[0_0_10px_rgba(251,191,36,0.3)]">
                              {performance.reduce((acc, curr) => acc + curr.duration, 0).toFixed(2)}s
                            </span>
                          </div>
                        </>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* WORKING MEMORY MD */}
            <div>
              <SectionHeader
                title="Working Memory MD"
                icon={<FileText className="w-3.5 h-3.5 text-amber-300 drop-shadow-[0_0_8px_rgba(251,191,36,0.8)]" />}
                isOpen={true}
                toggle={() => {}}
                count={workingMemory.trim() ? 1 : 0}
              />
              <div className="pt-2 pb-3">
                {workingMemory.trim() ? (
                  <div className="rounded-2xl border border-amber-400/20 bg-black/20 backdrop-blur-md p-3 text-[11px] leading-relaxed text-white/80 whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar">
                    {workingMemory}
                  </div>
                ) : (
                  <div className="text-white/40 text-[11px] italic px-2">No working memory markdown generated yet.</div>
                )}
              </div>
            </div>

            {/* WORKSPACE */}
            <div>
              <SectionHeader
                title="Workspace"
                icon={<FolderCode className="w-3.5 h-3.5 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]" />}
                isOpen={openWorkspace}
                toggle={() => setOpenWorkspace(!openWorkspace)}
                count={workspaceFiles.length}
              />
              <AnimatePresence>
                {openWorkspace && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-2 pb-3 space-y-1">
                      {workspaceFiles.length === 0 ? (
                        <div className="text-white/40 text-[11px] italic px-2">Local sandbox is empty.</div>
                      ) : (
                        workspaceFiles.map((f, i) => (
                          <div
                            key={i}
                            onClick={() => openFilePreview(f.name)}
                            className="flex items-center justify-between py-2 px-3 rounded-xl hover:bg-white/10 cursor-pointer transition-all group border border-transparent hover:border-white/20 hover:shadow-lg backdrop-blur-sm"
                          >
                            <div className="flex items-center gap-3 overflow-hidden">
                              <div className="w-7 h-7 flex-shrink-0 rounded-lg bg-black/20 flex items-center justify-center border border-white/5 group-hover:bg-emerald-500/20 transition-colors">
                                <FileText className="w-3.5 h-3.5 text-emerald-300 drop-shadow-[0_0_5px_rgba(110,231,183,1)]" />
                              </div>
                              <span className="text-white/80 truncate text-[13px] font-medium group-hover:text-white transition-colors drop-shadow-sm pr-2">{f.name}</span>
                            </div>
                            <button
                              onClick={(e) => deleteWorkspaceFile(e, f.name)}
                              className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-lg opacity-0 group-hover:opacity-100 hover:bg-rose-500/20 text-rose-300 transition-all border border-transparent hover:border-rose-500/30"
                              title="Delete File"
                            >
                              <Trash2 className="w-3.5 h-3.5 drop-shadow-md" />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* SKILLS */}
            <div>
              <SectionHeader
                title="Enabled Skills"
                icon={<Library className="w-3.5 h-3.5 text-fuchsia-400 drop-shadow-[0_0_8px_rgba(232,121,249,0.8)]" />}
                isOpen={openSkills}
                toggle={() => setOpenSkills(!openSkills)}
                count={skills.length}
              />
              <AnimatePresence>
                {openSkills && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-2 pb-3 space-y-2">
                      {skills.length === 0 ? (
                        <div className="text-white/40 text-[11px] italic px-2">No active workflows.</div>
                      ) : (
                        skills.map((s, i) => (
                          <div key={i} className="bg-black/20 backdrop-blur-md border border-white/10 rounded-2xl p-3.5 flex flex-col gap-1.5 hover:border-white/30 hover:bg-white/5 hover:shadow-[0_10px_30px_rgba(232,121,249,0.15)] transition-all relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-20 h-20 bg-fuchsia-500/20 rounded-full blur-2xl transform translate-x-1/2 -translate-y-1/2 opacity-50 group-hover:opacity-100 transition-opacity" />
                            <div className="font-semibold text-white/90 text-sm flex items-center justify-between z-10 drop-shadow-sm">
                              <span className="truncate pr-2">{s.name}</span>
                              <CheckCircle2 className="w-4 h-4 text-fuchsia-400 flex-shrink-0 drop-shadow-[0_0_5px_rgba(232,121,249,0.8)]" />
                            </div>
                            <div className="text-[11px] text-white/60 leading-relaxed line-clamp-2 z-10 group-hover:text-white/80 transition-colors">{s.description}</div>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* MCP TOOLS */}
            <div>
              <SectionHeader
                title="Context Tools"
                icon={<Wrench className="w-3.5 h-3.5 text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.8)]" />}
                isOpen={openTools}
                toggle={() => setOpenTools(!openTools)}
                count={tools.length}
              />
              <AnimatePresence>
                {openTools && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-2 pb-3 space-y-1 flex flex-wrap gap-2">
                      {tools.length === 0 ? (
                        <div className="text-white/40 text-[11px] italic px-2">No tools connected.</div>
                      ) : (
                        tools.map((t, i) => (
                          <div key={i} className="flex items-center gap-1.5 py-1.5 px-3 rounded-xl bg-black/30 border border-white/10 text-white/80 hover:bg-white/10 hover:border-white/20 transition-colors backdrop-blur-sm cursor-default hover:shadow-lg">
                            <span className="text-[11px] font-mono tracking-wide">{t.name}</span>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* MEMORY */}
            <div>
              <SectionHeader
                title="Memory Core"
                icon={<BrainCircuit className="w-3.5 h-3.5 text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]" />}
                isOpen={openMemory}
                toggle={() => setOpenMemory(!openMemory)}
                count={memory.length}
              />
              <AnimatePresence>
                {openMemory && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-2 pb-3 space-y-2">
                      <div className="flex items-center gap-2 px-1 pb-1">
                        <button
                          onClick={clearAtomicMemory}
                          disabled={clearingAtomic}
                          className="text-[10px] px-2.5 py-1.5 rounded-lg border border-rose-400/30 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20 transition-colors disabled:opacity-60"
                          title="Clear L1 atomic JSON memory"
                        >
                          {clearingAtomic ? "Clearing..." : "Clear Atomic"}
                        </button>
                        <button
                          onClick={clearWorkingMemory}
                          disabled={clearingWorking}
                          className="text-[10px] px-2.5 py-1.5 rounded-lg border border-amber-400/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20 transition-colors disabled:opacity-60"
                          title="Clear L2 memory.md working memory"
                        >
                          {clearingWorking ? "Clearing..." : "Clear Working MD"}
                        </button>
                      </div>
                      {memory.length === 0 ? (
                        <div className="text-white/40 text-[11px] italic px-2">Entity state is empty.</div>
                      ) : (
                        memory.map((m, i) => (
                          <div key={i} className="pl-3.5 py-1.5 border-l-2 border-cyan-400/50 group hover:border-cyan-400 transition-colors bg-gradient-to-r hover:from-cyan-500/10 hover:to-transparent rounded-r-lg">
                            <div className="text-[10px] text-cyan-300 font-mono uppercase mb-0.5 tracking-wider font-semibold drop-shadow-[0_0_3px_rgba(103,232,249,0.8)]">{m.category}</div>
                            <div className="text-xs text-white/70 leading-snug group-hover:text-white/90 transition-colors">{m.content}</div>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

          </>
        )}
      </div>

      <AnimatePresence>
        {previewFile && (
          <FilePreview
            isOpen={!!previewFile}
            filename={previewFile.name}
            content={previewFile.content}
            onClose={() => setPreviewFile(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
