import { useLayoutEffect, useRef, useState } from "react";
import {
  Bot,
  FileUp,
  Home,
  LogOut,
  MessageSquareText,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  UserCog,
  X,
  Pencil,
  Search,
  Trash2,
} from "lucide-react";
import type { AuthUser } from "../types/auth";
import type { AppPage } from "../layouts/AppLayout";
import { useTranslation } from "react-i18next";
import type { ConversationSummary } from "../services/conversationService";
import "../styles/sidebar.css";
import { canManageKnowledge, canManageUsers } from "../lib/permissions";
import { sectionCopy } from "../locales/copy";

interface SidebarV2Props {
  currentUser: AuthUser | null;
  activePage: AppPage;
  mobileOpen: boolean;
  setActivePage: (page: AppPage) => void;
  onCloseMobile: () => void;
  onLogout: () => void;
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onNewConversation: () => void;
  onSelectConversation: (id: string) => void;
  onRenameConversation: (item: ConversationSummary) => void;
  onDeleteConversation: (item: ConversationSummary) => void;
}

export default function SidebarV2({
  activePage,
  currentUser,
  mobileOpen,
  onCloseMobile,
  onLogout,
  setActivePage,
  conversations,
  activeConversationId,
  onNewConversation,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
}: SidebarV2Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [menuQuery, setMenuQuery] = useState("");
  const asideRef = useRef<HTMLElement>(null);
  const mobileCloseRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const { i18n, t } = useTranslation();
  const isFa = i18n.language.startsWith("fa");
  const labels = sectionCopy(t, "sidebar", ["home", "upload", "assistants", "users", "settings", "newChat", "recent", "navigation", "search", "collapse", "account"]);
  const navigation = [
    { id: "home" as const, label: labels.home, icon: Home },
    ...(canManageKnowledge(currentUser) ? [{ id: "upload" as const, label: labels.upload, icon: FileUp }] : []),
    { id: "assistants" as const, label: labels.assistants, icon: Bot },
    ...(canManageUsers(currentUser) ? [{ id: "users" as const, label: labels.users, icon: UserCog }] : []),
    { id: "settings" as const, label: labels.settings, icon: Settings },
  ];
  const normalizedQuery = menuQuery.trim().toLocaleLowerCase();
  const visibleNavigation = normalizedQuery ? navigation.filter((item) => item.label.toLocaleLowerCase().includes(normalizedQuery)) : navigation;
  const visibleConversations = normalizedQuery ? conversations.filter((item) => item.title.toLocaleLowerCase().includes(normalizedQuery)) : conversations;

  const closeLabel = isFa ? "بستن منو" : "Close navigation";
  const expandLabel = isFa ? "بازکردن منو" : "Expand sidebar";

  useLayoutEffect(() => {
    if (!mobileOpen) {
      const element = restoreFocusRef.current;
      restoreFocusRef.current = null;
      if (element) window.setTimeout(() => element.focus(), 0);
      return;
    }
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusTimer = window.setTimeout(() => mobileCloseRef.current?.focus(), 0);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseMobile();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(asideRef.current?.querySelectorAll<HTMLElement>("button, input, select, textarea, a[href]") ?? [])
        .filter((element) => !element.hasAttribute("disabled") && element.getClientRects().length > 0);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen, onCloseMobile]);

  return (
    <>
      <button
        type="button"
        aria-label={closeLabel}
        onClick={onCloseMobile}
        tabIndex={-1}
        aria-hidden="true"
        className={`nexora-sidebar-backdrop ${mobileOpen ? "is-open" : ""}`}
      />
      <aside
        ref={asideRef}
        dir={isFa ? "rtl" : "ltr"}
        role={mobileOpen ? "dialog" : undefined}
        aria-label={isFa ? "منوی اصلی" : "Main sidebar"}
        aria-modal={mobileOpen ? "true" : undefined}
        className={`nexora-sidebar ${collapsed ? "is-collapsed" : ""} ${mobileOpen ? "is-open" : ""}`}
      >
        <header className="nexora-sidebar__brand" dir="ltr">
          <div className="nexora-sidebar__brand-lockup">
            <img src="/brand/nexora-symbol.svg" alt="" width={30} height={30} />
            <div className="nexora-sidebar__expanded nexora-sidebar__wordmark">
              <strong>Nexora</strong>
              <span>by elmira</span>
            </div>
          </div>
          <button type="button" onClick={() => { setCollapsed((value) => !value); setMenuQuery(""); }} aria-label={collapsed ? expandLabel : labels.collapse} aria-expanded={!collapsed} title={collapsed ? expandLabel : labels.collapse} className="nexora-sidebar__collapse">
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
          <button ref={mobileCloseRef} type="button" onClick={onCloseMobile} className="nexora-sidebar__icon-button nexora-sidebar__mobile-close" aria-label={closeLabel}>
            <X size={18} />
          </button>
        </header>

        <div className="nexora-sidebar__tools">
          <label className="nexora-sidebar__search nexora-sidebar__expanded">
            <Search size={16} aria-hidden="true" />
            <input aria-label={labels.search} value={menuQuery} onChange={(event) => setMenuQuery(event.target.value)} placeholder={labels.search} />
            {menuQuery && <button type="button" onClick={() => setMenuQuery("")} aria-label={isFa ? "پاک‌کردن فیلتر ناوبری" : "Clear navigation filter"}><X size={14} /></button>}
          </label>
          <button type="button" onClick={onNewConversation} className="nexora-sidebar__new" title={labels.newChat} aria-label={labels.newChat}>
            <Plus size={18} aria-hidden="true" />
            <span className="nexora-sidebar__expanded">{labels.newChat}</span>
          </button>
        </div>

        <div className="nexora-sidebar__body">
          <nav className="nexora-sidebar__navigation" aria-label={labels.navigation}>
            <h2 className="nexora-sidebar__section-label nexora-sidebar__expanded">{labels.navigation}</h2>
            {visibleNavigation.map(({ id, icon: Icon, label }) => (
              <button
                key={id} type="button" title={label} aria-label={label}
                aria-current={activePage === id ? "page" : undefined}
                onClick={() => setActivePage(id)}
                className={`nexora-sidebar__nav-item ${activePage === id ? "is-active" : ""}`}
              >
                <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
                <span className="nexora-sidebar__expanded">{label}</span>
              </button>
            ))}
          </nav>

          <section className="nexora-sidebar__recent nexora-sidebar__expanded" aria-label={labels.recent}>
            <div className="nexora-sidebar__recent-heading">
              <h2 className="nexora-sidebar__section-label">{labels.recent}</h2>
              <span className="nexora-sidebar__count">{visibleConversations.length.toLocaleString(isFa ? "fa" : "en")}</span>
            </div>
            <div className="nexora-sidebar__recent-list" tabIndex={0} role="region" aria-label={labels.recent}>
            {visibleConversations.map((chat) => (
              <div key={chat.id} className={`nexora-sidebar__conversation ${activePage === "chat" && activeConversationId === chat.id ? "is-active" : ""}`}>
                <button onClick={() => onSelectConversation(chat.id)} type="button" title={chat.title} aria-current={activePage === "chat" && activeConversationId === chat.id ? "page" : undefined} className="nexora-sidebar__conversation-link">
                  <MessageSquareText size={17} strokeWidth={1.7} aria-hidden="true" />
                  <span>{chat.title}</span>
                </button>
                <div className="nexora-sidebar__conversation-actions">
                  <button type="button" onClick={() => onRenameConversation(chat)} aria-label={`${isFa ? "تغییر نام" : "Rename"}: ${chat.title}`} className="nexora-sidebar__icon-button"><Pencil size={13} /></button>
                  <button type="button" onClick={() => onDeleteConversation(chat)} aria-label={`${isFa ? "حذف" : "Delete"}: ${chat.title}`} className="nexora-sidebar__icon-button nexora-sidebar__delete"><Trash2 size={13} /></button>
                </div>
              </div>
            ))}
            {!visibleConversations.length && <p className="nexora-sidebar__empty">{normalizedQuery ? (isFa ? "نتیجه‌ای پیدا نشد" : "No results found") : (isFa ? "هنوز گفتگویی وجود ندارد" : "No conversations yet")}</p>}
            </div>
          </section>
        </div>

        <footer className="nexora-sidebar__footer">
          <div className="nexora-sidebar__account">
            <span className="nexora-sidebar__avatar" title={currentUser?.username}>{currentUser?.username.slice(0, 2) ?? "U"}</span>
            <div className="nexora-sidebar__account-copy nexora-sidebar__expanded">
              <strong>{currentUser?.username ?? "User"}</strong>
              <span title={currentUser?.organization_name}>{currentUser?.organization_name ?? "Workspace"} · {currentUser?.role ?? "user"}</span>
            </div>
            <button type="button" onClick={onLogout} aria-label={isFa ? "خروج از حساب" : "Log out"} title={isFa ? "خروج از حساب" : "Log out"} className="nexora-sidebar__icon-button nexora-sidebar__logout"><LogOut size={16} /></button>
          </div>
        </footer>
      </aside>
    </>
  );
}
