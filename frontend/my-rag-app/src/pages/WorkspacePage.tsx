import "../styles/workspace.css";
import { BookOpen, Clock3, MessageSquareText, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ConversationSummary } from "../services/conversationService";
import type { AuthUser } from "../types/auth";
import { canManageKnowledge } from "../lib/permissions";

interface WorkspacePageProps {
  currentUser: AuthUser | null;
  conversations: ConversationSummary[];
  onNewConversation: () => void;
  onOpenConversation: (id: string) => void;
  onOpenKnowledge: () => void;
}

export default function WorkspacePage({ currentUser, conversations, onNewConversation, onOpenConversation, onOpenKnowledge }: WorkspacePageProps) {
  const { i18n } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const recentConversations = conversations.slice(0, 5);
  const showKnowledgeManagement = canManageKnowledge(currentUser);

  return <div dir={isFa ? "rtl" : "ltr"} className="workspace-page h-full overflow-y-auto px-4 py-6 sm:px-7 lg:px-10">
    <div className="mx-auto max-w-5xl">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-[.1em] workspace-eyebrow">{isFa ? "فضای کاری" : "Workspace"}</span>
          <h1 className="mt-2 text-2xl font-semibold tracking-[-.025em] sm:text-3xl">{isFa ? `خوش آمدید، ${currentUser?.username ?? "کاربر"}` : `Welcome back, ${currentUser?.username ?? "there"}`}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 workspace-muted">{isFa ? "گفتگوهای اخیر را ادامه دهید یا یک پرسش تازه را با منابع سازمانی شروع کنید." : "Continue a recent conversation or start a new question grounded in your organization’s knowledge."}</p>
        </div>
        <button type="button" onClick={onNewConversation} className="workspace-primary inline-flex h-11 items-center justify-center gap-2 px-4 text-sm font-semibold"><Plus size={17} />{isFa ? "گفتگوی جدید" : "New conversation"}</button>
      </header>

      <section className={`mt-8 grid gap-4 ${showKnowledgeManagement ? "sm:grid-cols-2" : ""}`}>
        <div className="workspace-card p-5">
          <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl workspace-icon"><MessageSquareText size={19} /></span><div><p className="text-2xl font-semibold">{conversations.length}</p><p className="text-xs workspace-muted">{isFa ? "گفتگوی ذخیره‌شده" : "Saved conversations"}</p></div></div>
        </div>
        {showKnowledgeManagement && <button type="button" onClick={onOpenKnowledge} className="workspace-card p-5 text-start transition hover:border-[#18c7f4]/30 hover:bg-[#18c7f4]/[.06]"><div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl workspace-icon"><BookOpen size={19} /></span><div><p className="text-sm font-semibold">{isFa ? "پایگاه دانش" : "Knowledge base"}</p><p className="mt-1 text-xs workspace-muted">{isFa ? "اسناد و مجموعه‌های دانش را مدیریت کنید" : "Manage source documents and knowledge sets"}</p></div></div></button>}
      </section>

      <section className="workspace-card mt-8 p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3"><div><h2 className="text-base font-semibold">{isFa ? "گفتگوهای اخیر" : "Recent conversations"}</h2><p className="mt-1 text-xs workspace-muted">{isFa ? "برای ادامه، یک گفتگو را انتخاب کنید." : "Select a conversation to continue where you left off."}</p></div><Clock3 size={18} className="workspace-muted" /></div>
        {recentConversations.length ? <div className="workspace-conversations mt-5">{recentConversations.map((conversation) => <button key={conversation.id} type="button" onClick={() => onOpenConversation(conversation.id)} className="workspace-conversation flex w-full items-center gap-3 py-3 text-start transition"><span className="grid size-8 shrink-0 place-items-center rounded-lg workspace-icon"><MessageSquareText size={15} /></span><span className="min-w-0 flex-1 truncate text-sm font-medium">{conversation.title}</span><span className="shrink-0 text-xs workspace-muted">{new Date(conversation.updated_at).toLocaleDateString(isFa ? "fa-IR" : "en", { month: "short", day: "numeric" })}</span></button>)}</div> : <div className="mt-5 rounded-xl border border-dashed border-white/[.1] px-5 py-8 text-center"><MessageSquareText className="mx-auto workspace-muted" size={22} /><p className="mt-3 text-sm workspace-muted">{isFa ? "هنوز گفتگویی ندارید." : "You have no conversations yet."}</p><button type="button" onClick={onNewConversation} className="workspace-link mt-4 text-sm font-semibold">{isFa ? "شروع گفتگوی جدید" : "Start a new conversation"}</button></div>}
      </section>
    </div>
  </div>;
}
