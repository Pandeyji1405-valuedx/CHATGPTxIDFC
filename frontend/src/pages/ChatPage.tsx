import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  sendMessage,
  getConversation,
  submitMessageFeedback,
} from "@/services/chatService";
import type { ChatMessage, Citation } from "@/types/chat";

const STARTER_QUESTIONS = [
  {
    title: "KYC Onboarding Requirements",
    desc: "What are the mandatory KYC requirements for onboarding new retail and corporate customers?",
    query: "What are the KYC requirements for onboarding new customers?",
    icon: "👤",
  },
  {
    title: "Single Borrower Exposure Limits",
    desc: "What are the current RBI prudential limits on exposure to a single borrower or group?",
    query: "What are the RBI exposure limits for a single borrower?",
    icon: "📊",
  },
  {
    title: "Periodic KYC Updation",
    desc: "What is the required frequency for periodic KYC updates based on customer risk categorization?",
    query: "What are the requirements for periodic KYC updates?",
    icon: "🔄",
  },
  {
    title: "Digital Lending Guidelines",
    desc: "Explain the key compliance rules and borrower disclosures required under RBI digital lending directions.",
    query: "Explain the relevant RBI requirements for digital lending.",
    icon: "📱",
  },
];

function CitationBadge({ citation, index }: { citation: Citation; index: number }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-slate-800 rounded-xl overflow-hidden my-2 bg-slate-950/80 text-xs transition-all">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-slate-900 transition-colors gap-2"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-bold text-indigo-400 font-mono text-[11px] bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20 shrink-0">
            SOURCE [{index + 1}]
          </span>
          <span className="font-semibold text-white truncate">{citation.document_title}</span>
          {citation.circular_number && (
            <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-[10px] font-mono shrink-0 border border-slate-700">
              {citation.circular_number}
            </span>
          )}
          <span className="text-slate-400 text-[11px] shrink-0">p. {citation.page_number}</span>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform duration-200 shrink-0 ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 py-3 bg-slate-950 border-t border-slate-800 space-y-2 text-[11px]">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-slate-300">
            <div><strong className="text-white">Document Title:</strong> {citation.document_title}</div>
            {citation.circular_number && <div><strong className="text-white">Circular Number:</strong> {citation.circular_number}</div>}
            <div><strong className="text-white">Version:</strong> v{citation.version_number}</div>
            <div><strong className="text-white">Page Number:</strong> Page {citation.page_number}</div>
            {citation.section && <div><strong className="text-white">Section:</strong> {citation.section}</div>}
            <div><strong className="text-white">Chunk ID:</strong> <span className="font-mono text-[10px] text-indigo-300">{citation.chunk_id}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "USER";
  const [feedbackRating, setFeedbackRating] = useState<"POSITIVE" | "NEGATIVE" | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [showReasonInput, setShowReasonInput] = useState(false);
  const [commentText, setCommentText] = useState("");

  const handleFeedback = async (rating: "POSITIVE" | "NEGATIVE") => {
    if (rating === "NEGATIVE" && !showReasonInput) {
      setFeedbackRating(rating);
      setShowReasonInput(true);
      return;
    }
    try {
      setFeedbackRating(rating);
      await submitMessageFeedback(msg.id, rating, commentText || undefined);
      setFeedbackSent(true);
      setShowReasonInput(false);
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  return (
    <div className={`flex gap-3 sm:gap-4 max-w-4xl w-full my-4 ${isUser ? "ml-auto justify-end" : "mr-auto justify-start"}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-glow mt-1">
          AI
        </div>
      )}

      <div className={`flex flex-col gap-2 max-w-[88%] sm:max-w-[82%] ${isUser ? "items-end" : "items-start"}`}>
        {!isUser && (
          <div className="flex items-center gap-2 mb-1">
            <span className="badge-emerald text-[10px]">
              <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Grounded Response
            </span>
            {msg.retrieval_type && (
              <span className="badge-slate text-[10px] font-mono">
                {msg.retrieval_type.toUpperCase()}
              </span>
            )}
          </div>
        )}

        <div
          className={`p-4 sm:p-5 rounded-2xl text-xs sm:text-sm leading-relaxed ${
            isUser
              ? "bg-gradient-to-br from-indigo-600 to-indigo-700 text-white shadow-md rounded-tr-none"
              : "bg-slate-900 border border-slate-800 text-slate-100 shadow-card rounded-tl-none"
          }`}
        >
          <div className="whitespace-pre-wrap font-sans">{msg.content}</div>

          {!isUser && msg.citations && msg.citations.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-800">
              <p className="text-[11px] font-bold uppercase tracking-wider text-indigo-300 mb-2">
                Governed RBI Citations ({msg.citations.length})
              </p>
              <div className="space-y-1">
                {msg.citations.map((c, idx) => (
                  <CitationBadge key={c.chunk_id || idx} citation={c} index={idx} />
                ))}
              </div>
            </div>
          )}
        </div>

        {!isUser && (
          <div className="flex flex-col gap-2 mt-1">
            <div className="flex items-center gap-3 text-[11px] text-slate-400 px-1">
              <span>Was this guidance helpful?</span>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleFeedback("POSITIVE")}
                  disabled={feedbackSent}
                  className={`p-1.5 rounded-lg border transition-all ${
                    feedbackRating === "POSITIVE"
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
                  }`}
                  title="Mark as Helpful"
                >
                  👍
                </button>
                <button
                  onClick={() => handleFeedback("NEGATIVE")}
                  disabled={feedbackSent}
                  className={`p-1.5 rounded-lg border transition-all ${
                    feedbackRating === "NEGATIVE"
                      ? "bg-rose-500/20 text-rose-400 border-rose-500/40"
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
                  }`}
                  title="Mark as Unhelpful"
                >
                  👎
                </button>
              </div>
              {feedbackSent && (
                <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1 animate-fade-in">
                  ✓ Feedback submitted
                </span>
              )}
            </div>

            {showReasonInput && !feedbackSent && (
              <div className="flex items-center gap-2 bg-slate-900 p-2 rounded-xl border border-slate-800 animate-fade-in text-xs w-full max-w-md">
                <input
                  type="text"
                  placeholder="Optional reason for unhelpful rating..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  className="input-saas py-1 px-3 text-xs flex-1"
                />
                <button
                  onClick={() => handleFeedback("NEGATIVE")}
                  className="btn-primary py-1 px-3 text-xs shrink-0"
                >
                  Submit
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 flex items-center justify-center font-bold text-xs shrink-0 mt-1">
          ME
        </div>
      )}
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex gap-4 max-w-4xl w-full my-4 mr-auto justify-start animate-fade-in">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-glow">
        AI
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-card flex items-center gap-3 rounded-tl-none text-xs text-slate-300">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce"></span>
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]"></span>
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]"></span>
        </div>
        <span>Searching indexed RBI regulatory master directions...</span>
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const convId = searchParams.get('c');

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeNavConvIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (convId) {
      if (activeNavConvIdRef.current === convId) {
        // Skip re-fetching for conversation we just created/updated locally
        activeNavConvIdRef.current = null;
        return;
      }
      getConversation(convId)
        .then((d) => setMessages(d.messages))
        .catch(() => setError("Failed to load conversation thread."));
    } else {
      setMessages([]);
    }
  }, [convId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || isLoading) return;
    setError(null);
    setInput("");
    const tempId = `temp-${Date.now()}`;
    const tempMsg: ChatMessage = { id: tempId, role: "USER", content: msg, created_at: new Date().toISOString() };
    setMessages((p) => [...p, tempMsg]);
    setIsLoading(true);
    try {
      const res = await sendMessage({ conversation_id: convId ?? undefined, message: msg });
      const asstMsg: ChatMessage = {
        id: res.message_id,
        role: "ASSISTANT",
        content: res.answer,
        retrieval_type: res.retrieval_type,
        citations: res.citations,
        created_at: res.created_at,
      };
      setMessages((p) => [...p.filter((m) => m.id !== tempId), tempMsg, asstMsg]);
      if (!convId && res.conversation_id) {
        activeNavConvIdRef.current = res.conversation_id;
        navigate(`/chat?c=${res.conversation_id}`, { replace: true });
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Unable to complete request. Please verify backend connectivity.");
      setMessages((p) => p.filter((m) => m.id !== tempId));
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, convId, navigate]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col min-w-0 bg-slate-950 text-slate-100 relative overflow-hidden">
      {/* Message Scroll Viewport */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 flex flex-col items-center">
        {messages.length === 0 ? (
          <div className="my-auto flex flex-col items-center justify-center text-center max-w-3xl mx-auto py-8 animate-fade-in">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-heading tracking-tight mb-3">
              How can I assist your compliance query today?
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xl mb-10 leading-relaxed">
              Query approved RBI Master Directions, Circulars, and Statutory Guidelines with 100% grounded evidence and version-aware citations.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full text-left">
              {STARTER_QUESTIONS.map((item) => (
                <button
                  key={item.title}
                  onClick={() => handleSend(item.query)}
                  className="card-saas-hover p-4 sm:p-5 flex flex-col justify-between group cursor-pointer text-left border border-slate-800"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xl">{item.icon}</span>
                      <span className="text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity text-sm font-bold">→</span>
                    </div>
                    <h3 className="font-heading font-bold text-white text-xs sm:text-sm mb-1 group-hover:text-indigo-300 transition-colors">
                      {item.title}
                    </h3>
                    <p className="text-slate-400 text-[11px] leading-relaxed line-clamp-2">
                      {item.desc}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="w-full max-w-4xl mx-auto">
            {messages.map((m) => <MessageBubble key={m.id} msg={m} />)}
          </div>
        )}

        {isLoading && <ThinkingBubble />}
        <div ref={messagesEndRef} />
      </div>

      {/* Permanently Pinned Input Composer Area */}
      <div className="shrink-0 p-4 bg-slate-950 border-t border-slate-800/90 z-30">
        <div className="max-w-4xl mx-auto">
          {error && (
            <div className="mb-3 p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-xl text-xs font-medium flex items-center justify-between animate-fade-in">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-rose-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="line-clamp-2">{error}</span>
              </div>
              <button
                onClick={() => setError(null)}
                className="text-rose-400 hover:text-white text-xs font-bold shrink-0 ml-2"
              >
                Dismiss
              </button>
            </div>
          )}

          <div className="flex items-end gap-3 bg-slate-900 border border-slate-800 rounded-2xl p-3 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all shadow-2xl">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a regulatory compliance question... (Enter to send, Shift+Enter for new line)"
              className="flex-1 bg-transparent border-none outline-none text-xs sm:text-sm text-white placeholder-slate-500 resize-none min-h-[44px] max-h-[160px] py-1 px-2 font-sans"
              rows={1}
              disabled={isLoading}
            />
            <button
              onClick={() => handleSend()}
              disabled={isLoading || !input.trim()}
              className="btn-primary p-3 rounded-xl shrink-0 shadow-glow"
              title="Send prompt"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              )}
            </button>
          </div>

          <div className="flex items-center justify-between mt-2.5 px-2 text-[10px] text-slate-500">
            <span>Grounded in approved RBI Master Directions & Circulars.</span>
            <span>Authenticated User: {user?.name || user?.email}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
