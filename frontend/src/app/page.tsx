import { Sidebar } from "@/components/Sidebar";
import { ChatArea } from "@/components/ChatArea";

export default function Home() {
  return (
    <>
      <div className="bg-aurora">
        <div className="bg-aurora-inner"></div>
      </div>
      
      <main className="flex h-screen w-full text-white overflow-hidden font-sans relative z-10 selection:bg-fuchsia-500/30 p-2 sm:p-4 gap-4">
        {/* Sidebar - Wrapped in Glass Panel */}
        <div className="h-full glass rounded-3xl overflow-hidden flex-shrink-0 relative shadow-[0_0_50px_rgba(0,0,0,0.5)]">
          <Sidebar />
        </div>
        
        {/* Main Chat Interface - Wrapped in Glass Panel */}
        <div className="flex-1 flex flex-col h-full glass rounded-3xl overflow-hidden relative shadow-[0_0_50px_rgba(0,0,0,0.5)]">
          <ChatArea />
        </div>
      </main>
    </>
  );
}
