import "../styles/team.css";
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Plus, Search, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import AddUserForm from "../components/AddUserForm";
import UserKnowledgeAccess from "../components/UserKnowledgeAccess";
import ActionableError from "../components/ActionableError";
import InlineError from "../components/InlineError";
import { confirmAction } from "../services/confirmation";
import { userService, type ManagedUser } from "../services/userService";
import { sectionCopy } from "../locales/copy";

const directoryOrder = (items: ManagedUser[]) => [...items].sort((left, right) => {
  const roleDifference = (left.role === "admin" ? 0 : 1) - (right.role === "admin" ? 0 : 1);
  if (roleDifference) return roleDifference;
  const createdDifference = new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
  return createdDifference || left.id.localeCompare(right.id);
});

export default function UsersPage() {
  const { i18n, t } = useTranslation(); const fa = i18n.language.startsWith("fa");
  const [users, setUsers] = useState<ManagedUser[]>([]); const [query, setQuery] = useState(""); const [role, setRole] = useState("all"); const [loading, setLoading] = useState(true); const [loadError, setLoadError] = useState<string | null>(null); const [actionError, setActionError] = useState(""); const [loadRevision, setLoadRevision] = useState(0); const [deleting, setDeleting] = useState<string | null>(null); const [showAddUser, setShowAddUser] = useState(false);
  const c = sectionCopy(t, "usersPage", ["eyebrow", "title", "subtitle", "add", "directory", "search", "all", "admin", "user", "active", "inactive", "remove"]);
  useEffect(() => {
    let cancelled = false;
    userService.list().then((items) => { if (!cancelled) { setUsers(directoryOrder(items)); setLoadError(null); } })
      .catch((error: Error) => { if (!cancelled) setLoadError(error.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fa, loadRevision]);
  const retryLoad = () => {
    setLoading(true);
    setLoadError(null);
    setLoadRevision((value) => value + 1);
  };
  const filtered = useMemo(() => directoryOrder(users.filter((u) => u.username.toLowerCase().includes(query.toLowerCase()) && (role === "all" || u.role === role))), [users, query, role]);
  const remove = async (user: ManagedUser) => {
    if (user.role === "admin" || deleting) return;
    setDeleting(user.id);
    try {
      const message = fa ? `عضو «${user.username}» حذف شود؟ حساب و داده‌های شخصی وابسته به آن حذف می‌شوند. این کار قابل بازگشت نیست.` : `Delete member “${user.username}”? Their account and associated personal data will be permanently deleted.`;
      if (!await confirmAction(message)) return;
      await userService.remove(user.id);
      setUsers((items) => items.filter((item) => item.id !== user.id));
      toast.success(fa ? "عضو حذف شد" : "Member deleted");
    } catch (e) { setActionError((e as Error).message); }
    finally { setDeleting(null); }
  };
  return <div dir={fa ? "rtl" : "ltr"} className="team-page relative flex h-full overflow-hidden"><main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8"><div className="mx-auto flex h-full max-w-[950px] flex-col"><header className="team-header flex shrink-0 items-end justify-between gap-4"><div><div className="team-eyebrow">{c.eyebrow}</div><h1 className="text-2xl font-semibold tracking-[-.025em]">{c.title}</h1><p className="mt-2 text-xs leading-6 tm-muted">{c.subtitle}</p></div><button type="button" onClick={() => { setActionError(""); setShowAddUser(true); }} className="team-primary flex h-10 shrink-0 items-center gap-2 px-4 text-xs font-semibold"><Plus size={15} />{c.add}</button></header><section className="app-glass-panel mt-6 flex min-h-0 flex-1 flex-col overflow-hidden rounded-[24px]"><div className="flex shrink-0 flex-col gap-3 border-b border-white/[.07] p-4 sm:flex-row sm:items-center sm:justify-between"><h2 className="text-sm font-semibold">{c.directory}</h2><div className="flex gap-2"><label className="relative flex-1 sm:w-60"><Search size={14} className="absolute start-3 top-1/2 -translate-y-1/2 tm-muted" /><input value={query} onChange={(e) => setQuery(e.target.value)} aria-label={c.search} placeholder={c.search} className="h-10 w-full rounded-xl border border-white/[.09] bg-white/[.035] ps-9 pe-3 text-xs outline-none placeholder:text-white/20" /></label><label className="relative"><select aria-label={c.all} value={role} onChange={(e) => setRole(e.target.value)} className="h-10 appearance-none rounded-xl border border-white/[.09] bg-[#0a1530] ps-3 pe-8 text-xs tm-muted"><option value="all">{c.all}</option><option value="admin">{c.admin}</option><option value="user">{c.user}</option></select><ChevronDown size={13} className="absolute end-2.5 top-1/2 -translate-y-1/2 tm-muted" /></label></div></div>{actionError && <div className="px-4 pt-3"><InlineError message={actionError} onDismiss={() => setActionError("")} /></div>}<div className="min-h-0 flex-1 divide-y divide-white/[.055] overflow-y-auto">{loading ? <div className="grid h-full place-items-center"><span role="status" aria-label={fa ? "در حال دریافت اعضا" : "Loading members"} className="size-5 animate-spin rounded-full border-2 border-white/10 border-t-[#c43cff]" /></div> : loadError ? <ActionableError error={loadError} operation="members" isFa={fa} title={fa ? "دریافت اعضا ناموفق بود" : "Members could not be loaded"} onRetry={retryLoad} /> : filtered.map((user) => <div key={user.id} className="team-member-row"><span className="team-avatar">{user.username.slice(0, 2)}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold tm-text">{user.username}</p><p className="team-member-details mt-1 text-xs tm-muted"><bdi className="team-member-job">{user.job_title || (fa ? "بدون عنوان شغلی" : "No job title")}</bdi><span aria-hidden="true">·</span><time dateTime={user.created_at} dir={fa ? "rtl" : "ltr"}>{new Intl.DateTimeFormat(fa ? "fa-IR" : "en", { dateStyle: "medium" }).format(new Date(user.created_at))}</time></p></div><div className="team-member-access">{user.role !== "admin" && <UserKnowledgeAccess user={user} isFa={fa} />}<span className={`team-role ${user.role === "admin" ? "is-admin" : ""}`}>{user.role === "admin" ? c.admin : c.user}</span></div><span className={`team-status ${user.is_active ? "is-active" : ""}`} aria-label={user.is_active ? c.active : c.inactive} title={user.is_active ? c.active : c.inactive} />{user.role !== "admin" && <button type="button" className="team-delete" disabled={deleting !== null} onClick={() => void remove(user)} aria-label={`${c.remove}: ${user.username}`} title={c.remove}><Trash2 size={15} aria-hidden="true" /><span>{deleting === user.id ? "…" : c.remove}</span></button>}</div>)}{!loading && !loadError && !filtered.length && <p className="team-empty">{fa ? "عضوی با این مشخصات پیدا نشد." : "No members match your search."}</p>}</div></section></div></main>
    {showAddUser && <AddUserForm isFa={fa} onClose={() => setShowAddUser(false)} onCreated={(user) => { setUsers((items) => directoryOrder([...items, user])); setShowAddUser(false); }} />}
  </div>;
}
