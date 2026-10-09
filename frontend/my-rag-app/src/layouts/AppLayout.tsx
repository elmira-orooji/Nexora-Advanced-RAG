import { confirmAction } from "../services/confirmation";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Menu } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import SidebarV2 from "../components/SidebarV2";
import NotificationCenter from "../components/NotificationCenter";
import InlineError from "../components/InlineError";
import InlineSuccessMessages from "../components/InlineSuccessMessages";
import LoadingSkeleton from "../components/LoadingSkeleton";
import RenameConversationDialog from "../components/RenameConversationDialog";
import { authService } from "../services/authService";
import { conversationService, type ConversationSummary } from "../services/conversationService";
import toast from "react-hot-toast";
import { canManageKnowledge, canManageUsers } from "../lib/permissions";
import { useTranslation } from "react-i18next";
import { getPreferredTheme, saveTheme, type Theme } from "../utils/theme";
import { useEntranceMotion } from "../lib/entranceMotion";

const AnalyticsPage = lazy(() => import("../pages/AnalyticsPage"));
const AssistantsPage = lazy(() => import("../pages/AssistantsPage"));
const ConversationPage = lazy(() => import("../pages/ConversationPage"));
const SettingsPage = lazy(() => import("../pages/SettingsPage"));
const UploadFilesPage = lazy(() => import("../pages/UploadFilesPage"));
const UsersPage = lazy(() => import("../pages/UsersPage"));
const WorkspacePage = lazy(() => import("../pages/WorkspacePage"));

function PageFallback() {
  return <LoadingSkeleton variant="page" />;
}

export type AppPage = "home" | "chat" | "upload" | "assistants" | "users" | "settings";

const PAGE_PATHS: Record<AppPage, string> = {
  home: "/home",
  chat: "/home/chat",
  upload: "/home/knowledge",
  assistants: "/home/assistants",
  users: "/home/users",
  settings: "/home/settings",
};

function routeState(pathname: string): { page: AppPage; conversationId: string | null; valid: boolean } {
  const segments = pathname.slice("/home".length).split("/").filter(Boolean);
  if (!segments.length) return { page: "home", conversationId: null, valid: true };
  if (segments[0] === "chat" && segments.length <= 2) {
    return { page: "chat", conversationId: segments[1] ?? null, valid: true };
  }
  const page = ({ knowledge: "upload", assistants: "assistants", users: "users", settings: "settings" } as const)[segments[0] as "knowledge" | "assistants" | "users" | "settings"];
  return page && segments.length === 1
    ? { page, conversationId: null, valid: true }
    : { page: "home", conversationId: null, valid: false };
}

export default function AppLayout() {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentUser = authService.getUser();
  const canManageKnowledgeSets = canManageKnowledge(currentUser);
  const { page: activePage, conversationId: activeConversationId, valid: validRoute } = routeState(location.pathname);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const closeMobileMenu = useCallback(() => setMobileMenuOpen(false), []);
  const [theme, setTheme] = useState<Theme>(getPreferredTheme);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationToRename, setConversationToRename] = useState<ConversationSummary | null>(null);
  const [inlineError, setInlineError] = useState("");
  const contentRef = useRef<HTMLElement>(null);
  useEntranceMotion(contentRef);

  const loadConversations = () => {
    conversationService.list().then(setConversations).catch((error) => setInlineError((error as Error).message));
  };

  useEffect(() => { loadConversations(); }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    if (mobileMenuOpen) content.setAttribute("inert", "");
    else content.removeAttribute("inert");
    return () => content.removeAttribute("inert");
  }, [mobileMenuOpen]);

  const selectPage = (page: AppPage) => {
    navigate(PAGE_PATHS[page]);
    setMobileMenuOpen(false);
  };

  const handleLogout = async () => {
    const message = i18n.language.startsWith("fa")
      ? "از حساب کاربری خارج می‌شوید؟"
      : "Do you want to log out?";
    if (!await confirmAction(message)) return;
    await authService.logout();
    navigate("/", { replace: true });
  };

  const newConversation = () => {
    navigate(PAGE_PATHS.chat);
    setMobileMenuOpen(false);
  };

  const startAssistantConversation = async (assistantId: string): Promise<boolean> => {
    try {
      const conversation = await conversationService.createForAssistant(assistantId);
      loadConversations();
      navigate(`${PAGE_PATHS.chat}/${encodeURIComponent(conversation.id)}`);
      return true;
    } catch (error) {
      setInlineError((error as Error).message);
      return false;
    }
  };

  const selectConversation = (id: string) => {
    navigate(`${PAGE_PATHS.chat}/${encodeURIComponent(id)}`);
    setMobileMenuOpen(false);
  };

  const renameConversation = async (title: string) => {
    if (!conversationToRename) return;
    await conversationService.rename(conversationToRename.id, title);
    setConversations((current) => current.map((item) => item.id === conversationToRename.id ? { ...item, title } : item));
    setConversationToRename(null);
    toast.success(t("conversationRename.success"));
  };

  const deleteConversation = async (item: ConversationSummary) => {
    if (!await confirmAction(`Delete “${item.title}”? This cannot be undone.`)) return;
    try {
      await conversationService.remove(item.id);
      if (activeConversationId === item.id) navigate(PAGE_PATHS.chat, { replace: true });
      loadConversations();
    } catch (error) { setInlineError((error as Error).message); }
  };

  return (
    <div className="app-shell flex h-[100dvh] overflow-hidden text-white">
      <SidebarV2
        activePage={activePage}
        currentUser={currentUser}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={closeMobileMenu}
        onLogout={() => void handleLogout()}
        setActivePage={selectPage}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onNewConversation={newConversation}
        onSelectConversation={selectConversation}
        onRenameConversation={setConversationToRename}
        onDeleteConversation={(item) => void deleteConversation(item)}
      />

      {conversationToRename && (
        <RenameConversationDialog
          conversation={conversationToRename}
          onClose={() => setConversationToRename(null)}
          onRename={renameConversation}
        />
      )}

      <section ref={contentRef} className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          <div className="app-orb absolute -right-24 -top-28 size-[30rem] rounded-full bg-[#7c27ff]/15 blur-[130px]" />
          <div className="app-orb app-orb-delayed absolute -bottom-36 left-[12%] size-[32rem] rounded-full bg-[#18c7f4]/10 blur-[150px]" />
          <div className="app-grid absolute inset-0" />
        </div>

        <header className="relative z-20 flex h-16 shrink-0 items-center justify-between border-b border-[#213157] bg-[#09132a]/80 px-4 backdrop-blur-xl md:hidden">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Open navigation"
            className="app-icon-button grid size-11 place-items-center rounded-xl"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <span className="grid size-8 place-items-center rounded-lg border border-[#c43cff]/20 bg-[#15123a] shadow-[0_0_24px_rgba(124,39,255,.3)]">
              <img src="/brand/nexora-symbol.svg" alt="" className="size-5" />
            </span>
            Nexora
          </div>
          <div className="flex items-center gap-2"><span className="grid size-10 place-items-center rounded-full border border-white/10 bg-white/[.06] text-xs font-bold uppercase">{currentUser?.username.slice(0, 2) ?? "U"}</span></div>
        </header>

        <InlineSuccessMessages />
        <main className="nexora-app-content relative z-10 min-h-0 flex-1 overflow-hidden">{inlineError && <div className="relative z-20 px-4 pt-3"><InlineError message={inlineError} onDismiss={() => setInlineError("")} /></div>}<Suspense fallback={<PageFallback />}>
          {!validRoute && <Navigate to="/home" replace />}
          {activePage === "home" && validRoute && (canManageUsers(currentUser) ? <AnalyticsPage notificationCenter={<NotificationCenter onNavigate={navigate} />} /> : <WorkspacePage currentUser={currentUser} conversations={conversations} onNewConversation={newConversation} onOpenConversation={selectConversation} onOpenKnowledge={() => selectPage("upload")} />)}
          {activePage === "chat" && validRoute && <ConversationPage key={activeConversationId ?? "new-conversation"} conversationId={activeConversationId} onConversationChange={(id) => navigate(`${PAGE_PATHS.chat}/${encodeURIComponent(id)}`, { replace: true })} onConversationsUpdated={loadConversations} onOpenKnowledge={(intent) => navigate(PAGE_PATHS.upload, { state: { knowledgeIntent: intent } })} />}
          {activePage === "upload" && (canManageKnowledgeSets ? <UploadFilesPage initialAction={location.state?.knowledgeIntent === "create" || location.state?.knowledgeIntent === "upload" ? location.state.knowledgeIntent : undefined} /> : <Navigate to="/home" replace />)}
          {activePage === "assistants" && <AssistantsPage onStartConversation={startAssistantConversation} />}
          {activePage === "users" && (canManageUsers(currentUser) ? <UsersPage /> : <Navigate to="/home" replace />)}
          {activePage === "settings" && <SettingsPage theme={theme} setTheme={setTheme} />}
        </Suspense></main>
      </section>
    </div>
  );
}
