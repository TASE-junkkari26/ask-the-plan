import { FileImage, FileText, X } from 'lucide-react';
import type { Language, LocalDrawing } from '../types';

export function fileSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ImportedDrawingList({
  drawings,
  activeId,
  language,
  onSelect,
  onRemove,
}: {
  drawings: LocalDrawing[];
  activeId: string | null;
  language: Language;
  onSelect: (drawing: LocalDrawing) => void;
  onRemove: (drawing: LocalDrawing) => void;
}) {
  return (
    <div className="imported-drawing-list">
      {drawings.map((drawing) => (
        <div
          key={drawing.id}
          className={`imported-drawing-row ${activeId === drawing.id ? 'active-drawing' : ''}`}
        >
          <button
            className="imported-file"
            onClick={() => onSelect(drawing)}
            aria-pressed={activeId === drawing.id}
            aria-label={`${language === 'fi' ? 'Esikatsele' : 'Preview'} ${drawing.file.name}`}
          >
            <span className="drawing-thumbnail">
              <img src={drawing.url} alt="" loading="lazy" draggable={false} />
            </span>
            <span className="imported-file-description">
              <strong title={drawing.file.name}>{drawing.file.name}</strong>
              <small>
                {drawing.kind === 'pdf' ? (
                  <FileText size={11} />
                ) : (
                  <FileImage size={11} />
                )}
                {drawing.kind === 'pdf'
                  ? `${drawing.pages} ${language === 'fi' ? 'sivua' : drawing.pages === 1 ? 'page' : 'pages'}`
                  : language === 'fi'
                    ? 'Kuva'
                    : 'Image'}
                <span>·</span>
                {fileSize(drawing.file.size)}
              </small>
            </span>
          </button>
          <button
            className="icon-button remove-import"
            onClick={() => onRemove(drawing)}
            aria-label={`${language === 'fi' ? 'Poista' : 'Remove'} ${drawing.file.name}`}
            title={
              language === 'fi'
                ? 'Poista paikallinen tiedosto'
                : 'Remove local file'
            }
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
