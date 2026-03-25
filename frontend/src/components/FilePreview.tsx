"use client";

import { X, FileCode2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion } from "framer-motion";

interface FilePreviewProps {
  isOpen: boolean;
  filename: string;
  content: string;
  onClose: () => void;
}

export function FilePreview({ isOpen, filename, content, onClose }: FilePreviewProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 lg:p-12">
      {/* Immersive Backdrop Overlay */}
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/40 backdrop-blur-2xl"
        onClick={onClose}
      />

      {/* Floating Glass Modal Surface */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 15 }}
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="relative bg-black/30 backdrop-blur-3xl border border-white/20 shadow-[0_20px_80px_rgba(0,0,0,0.8)] rounded-3xl w-full max-w-5xl h-full max-h-[85vh] flex flex-col overflow-hidden ring-1 ring-white/10"
      >
        {/* Luminous upper gradient edge */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-fuchsia-400/50 to-transparent z-20" />

        {/* Header Ribbon */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.03] z-10">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center shadow-inner relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-br from-cyan-400/20 to-fuchsia-500/20 opacity-0 group-hover:opacity-100 transition-opacity" />
              <FileCode2 className="w-5 h-5 text-cyan-300 drop-shadow-[0_0_8px_rgba(103,232,249,0.8)] relative z-10" />
            </div>
            <div>
              <h2 className="text-[15px] font-bold text-white tracking-tight drop-shadow-sm">{filename}</h2>
              <p className="text-[11px] text-white/50 font-mono mt-0.5 tracking-wider uppercase">workspace/{filename}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-all border border-transparent hover:border-white/10 active:scale-90"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Viewport */}
        <div className="flex-1 overflow-y-auto p-8 lg:p-12 text-white custom-scrollbar relative">
          <div className="absolute top-0 right-0 w-96 h-96 bg-fuchsia-500/10 rounded-full blur-[100px] pointer-events-none -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-[100px] pointer-events-none translate-y-1/2 -translate-x-1/2" />
          
          <div className="prose prose-invert prose-p:leading-[1.8] prose-p:text-[15px] prose-p:text-white/90 prose-pre:bg-black/50 prose-pre:backdrop-blur-xl prose-pre:border prose-pre:border-white/10 prose-pre:shadow-2xl prose-pre:rounded-2xl max-w-none prose-headings:text-white prose-headings:font-bold prose-heading:tracking-tight prose-a:text-cyan-400 hover:prose-a:text-cyan-300 prose-code:text-cyan-200 prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-li:text-white/90 relative z-10 drop-shadow-sm">
            {filename.endsWith(".md") || filename.endsWith(".mdx") ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            ) : (
              <pre className="text-[13px] text-white/90 font-mono whitespace-pre-wrap leading-[1.7] border border-white/5 rounded-2xl p-6 bg-black/40 backdrop-blur-md shadow-inner">{content}</pre>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
