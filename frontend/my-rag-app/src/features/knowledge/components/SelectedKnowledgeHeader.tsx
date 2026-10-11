import { useState } from "react";
import { Link2, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import type { DocumentSet } from "../../../services/knowledgeService";

interface Props {
  item: DocumentSet;
  isAdmin: boolean;
  isFa: boolean;
  labels: { connect: string; edit: string; delete: string };
  onConnect: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export default function SelectedKnowledgeHeader({ item, isAdmin, isFa, labels, onConnect, onEdit, onDelete }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const canManage = isAdmin || item.access_level === "manage";
  const canEdit = canManage || item.access_level === "edit";
  const descriptionId = `set-description-${item.id}`;

  const edit = () => {
    setMenuOpen(false);
    onEdit();
  };

  return (
    <div className="kb-selected-set-header flex shrink-0 items-center justify-between gap-3">
      <div className="min-w-0 flex-1">
        <h2 className="nexora-file-name text-lg font-semibold">{item.name}</h2>
        {item.description && (
          <div className="kb-description-preview mt-1">
            <p id={descriptionId} className={`text-xs kb-muted ${expanded ? "kb-description-expanded" : "nexora-file-name"}`}>
              {item.description}
            </p>
            <button type="button" className="kb-description-toggle" aria-expanded={expanded} aria-controls={descriptionId} onClick={() => setExpanded(!expanded)}>
              {expanded ? (isFa ? "بستن" : "Show less") : (isFa ? "ادامه" : "Read more")}
            </button>
          </div>
        )}
      </div>
      <div className="kb-selected-set-actions flex shrink-0 items-center gap-2">
        {canEdit && (
          <button type="button" onClick={onConnect} className="kb-connect flex h-9 items-center gap-1.5 px-3 text-xs font-medium">
            <Link2 size={13} />{labels.connect}
          </button>
        )}
        {canManage && (
          <div className="relative">
            <button type="button" aria-label={isFa ? "گزینه‌های مجموعه" : "Set options"} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)} className="app-icon-button grid size-9 place-items-center rounded-xl kb-muted">
              <MoreHorizontal size={17} />
            </button>
            {menuOpen && (
              <div className="kb-set-menu nexora-dropdown absolute end-0 top-11 z-30 w-40 p-1.5">
                <button type="button" onClick={edit} className="kb-set-menu-item"><Pencil size={13} />{labels.edit}</button>
                <button type="button" onClick={onDelete} className="kb-set-menu-item is-danger"><Trash2 size={13} />{labels.delete}</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
