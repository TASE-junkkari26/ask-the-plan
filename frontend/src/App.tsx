import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import type {
  ChangeEvent,
  DragEvent as ReactDragEvent,
  PointerEvent as ReactPointerEvent,
} from 'react';
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleHelp,
  Expand,
  FileImage,
  FileText,
  FolderOpen,
  LayoutGrid,
  Minus,
  MousePointer2,
  PanelRightClose,
  Plus,
  RotateCw,
  ScanLine,
  Search,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import {
  ImportedDrawingList,
  fileSize,
} from './components/ImportedDrawingList';
import { ViewerBoundary } from './components/ViewerBoundary';
import { clampZoom } from './lib/viewport';
import { importDocument, releaseDrawing } from './lib/importDocument';
import {
  importSource,
  releaseSource,
  SOURCE_ACCEPT,
  SOURCE_FORMATS,
} from './lib/importSource';
import { ifcCache } from './ifc/cache';
import type { IfcStatus, Language, LocalDrawing, LocalSource } from './types';

const IfcWorkbench = lazy(() => import('./components/IfcWorkbench'));

const copy = {
  en: {
    drawings: 'Drawings',
    search: 'Find a drawing…',
    current: 'Current drawing',
    ask: 'Ask the drawing',
    intro: 'Questions about your selected drawing.',
    placeholder: 'Ask about this drawing…',
    askButton: 'Ask question',
    only: 'Based only on the selected drawing',
    export: 'Export SVG',
    local: 'Local preview',
    help: 'How it works',
    import: 'Import drawings',
    drop: 'or drag and drop them here',
    select: 'Select files',
    localFiles: 'Your imports',
    localNote: 'Files stay in this tab. Refreshing clears the imports.',
    dropTitle: 'Drop drawings to import',
    importErrors: 'Some files could not be opened',
    welcome: 'Start with a drawing.',
    welcomeIntro: 'Import a drawing to open your workspace.',
    formats: 'PDF and images · Up to 35 MiB per file · IFC · Up to 100 MiB',
    opening: 'Opening your drawing…',
    chatUnavailable:
      'Question answering for imported drawings is not available yet.',
  },
  fi: {
    drawings: 'Piirustukset',
    search: 'Etsi piirustusta…',
    current: 'Valittu piirustus',
    ask: 'Kysy piirustukselta',
    intro: 'Kysymyksiä valitusta piirustuksesta.',
    placeholder: 'Kysy tästä piirustuksesta…',
    askButton: 'Kysy',
    only: 'Perustuu vain valittuun piirustukseen',
    export: 'Vie SVG',
    local: 'Paikallinen esikatselu',
    help: 'Miten tämä toimii',
    import: 'Tuo piirustuksia',
    drop: 'tai pudota ne tähän',
    select: 'Valitse tiedostot',
    localFiles: 'Omat tiedostot',
    localNote:
      'Tiedostot säilyvät tässä välilehdessä sivun päivittämiseen asti.',
    dropTitle: 'Pudota tuotavat piirustukset',
    importErrors: 'Joitakin tiedostoja ei voitu avata',
    welcome: 'Aloita piirustuksesta.',
    welcomeIntro: 'Tuo piirustus avataksesi työtilan.',
    formats: 'PDF- ja kuvatiedostot · Enintään 35 MiB / tiedosto · IFC · Enintään 100 MiB',
    opening: 'Avataan piirustusta…',
    chatUnavailable:
      'Tuotuja piirustuksia koskeviin kysymyksiin ei vielä voi vastata.',
  },
};

type ImportError = { name: string; message: string };

function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <ScanLine size={20} strokeWidth={1.7} />
      </span>
      <span className="brand-wordmark">
        ask<span className="brand-light">the</span>plan
      </span>
    </span>
  );
}

function HelpDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      className="help-dialog"
      ref={ref}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <button
        className="icon-button dialog-close"
        aria-label="Close help"
        onClick={onClose}
      >
        <X size={18} />
      </button>
      <span className="feature-icon">
        <Upload size={25} />
      </span>
      <h2>Your drawing, in focus.</h2>
      <p>
        Select or drop an image, PDF, or IFC file to open it. Explore drawings
        with the chat panel, or inspect a model in 3D. Use Drawings to switch
        files or remove an import.
      </p>
      <div className="help-note">
        <FileImage size={17} />
        <span>
          Files are previewed locally and cleared on refresh. Question answering
          for imported drawings is not available yet.
        </span>
      </div>
      <div className="shortcut-grid">
        <span>Zoom</span>
        <span>
          <kbd>+</kbd> <kbd>−</kbd> or scroll
        </span>
        <span>Fit drawing</span>
        <kbd>0</kbd>
        <span>Rotate drawing</span>
        <kbd>R</kbd>
        <span>Find a drawing</span>
        <kbd>/</kbd>
      </div>
      <button className="primary-button" onClick={onClose}>
        Got it <ArrowRight size={16} />
      </button>
    </dialog>
  );
}

function ImportErrors({
  errors,
  language,
  onDismiss,
}: {
  errors: ImportError[];
  language: Language;
  onDismiss: () => void;
}) {
  if (!errors.length) return null;
  return (
    <section
      className="import-errors"
      role="alert"
      aria-label={copy[language].importErrors}
    >
      <div>
        <CircleAlert size={15} />
        <strong>{copy[language].importErrors}</strong>
        <button
          className="icon-button"
          onClick={onDismiss}
          aria-label={
            language === 'fi' ? 'Sulje tuontivirheet' : 'Dismiss import errors'
          }
        >
          <X size={14} />
        </button>
      </div>
      <ul>
        {errors.map((error, index) => (
          <li key={index}>
            <strong>{error.name}</strong>
            <span>{error.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function App() {
  const [language, setLanguage] = useState<Language>('en');
  const t = copy[language];
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [paperWidth, setPaperWidth] = useState(800);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [helpOpen, setHelpOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [localDrawings, setLocalDrawings] = useState<LocalSource[]>([]);
  const [activeImportId, setActiveImportId] = useState<string | null>(null);
  const [ifcEpoch, setIfcEpoch] = useState(0);
  const [ifcInspectorHost, setIfcInspectorHost] =
    useState<HTMLDivElement | null>(null);
  const activeSource =
    localDrawings.find((source) => source.id === activeImportId) ?? null;
  const imported =
    activeSource && activeSource.kind !== 'ifc' ? activeSource : null;
  const ifcSource = activeSource?.kind === 'ifc' ? activeSource : null;
  const ifcActive = ifcSource !== null;
  const hasDrawing = activeSource !== null;
  const title = activeSource?.file.name ?? '';
  const [importProgress, setImportProgress] = useState<{
    name: string;
    current: number;
    total: number;
  } | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const importing = importProgress !== null || pageLoading;
  const [importErrors, setImportErrors] = useState<ImportError[]>([]);
  const [fileDragging, setFileDragging] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const drawingDialogRef = useRef<HTMLDialogElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const activeImportIdRef = useRef<string | null>(null);
  const viewVersion = useRef(0);
  const localDrawingsRef = useRef<LocalSource[]>([]);
  const batchRef = useRef<AbortController | null>(null);
  const pageRef = useRef<AbortController | null>(null);
  const fileDragDepth = useRef(0);
  const localId = useRef(0);
  const dragRef = useRef<{
    x: number;
    y: number;
    pan: { x: number; y: number };
  } | null>(null);

  useEffect(() => {
    const stage = stageRef.current;
    if (ifcActive || !stage) return;
    const observer = new ResizeObserver(([entry]) => {
      const compact = entry.contentRect.width < 600;
      setPaperWidth(
        Math.max(
          220,
          Math.min(
            entry.contentRect.width - (compact ? 32 : 48),
            ((entry.contentRect.height - (compact ? 80 : 88)) * 1100) / 780,
            1100,
          ),
        ),
      );
    });
    observer.observe(stage);
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom((value) => clampZoom(value * Math.exp(-event.deltaY * 0.001)));
    };
    stage.addEventListener('wheel', wheel, { passive: false });
    return () => {
      observer.disconnect();
      stage.removeEventListener('wheel', wheel);
    };
  }, [hasDrawing, inspectorOpen, ifcActive]);
  useEffect(() => {
    if (sidebarOpen) {
      drawingDialogRef.current?.showModal();
      searchRef.current?.focus();
    }
  }, [sidebarOpen]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 4400);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const endFileDrag = () => {
      fileDragDepth.current = 0;
      setFileDragging(false);
    };
    window.addEventListener('dragend', endFileDrag);
    window.addEventListener('drop', endFileDrag);
    window.addEventListener('blur', endFileDrag);
    return () => {
      window.removeEventListener('dragend', endFileDrag);
      window.removeEventListener('drop', endFileDrag);
      window.removeEventListener('blur', endFileDrag);
    };
  }, []);
  useEffect(
    () => () => {
      batchRef.current?.abort();
      batchRef.current = null;
      pageRef.current?.abort();
      pageRef.current = null;
      localDrawingsRef.current.forEach(releaseSource);
      ifcCache.clear();
      localDrawingsRef.current = [];
    },
    [],
  );
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSidebarOpen(false);
      if ((event.target as HTMLElement).closest('input, textarea, dialog'))
        return;
      if (
        event.key === '/' ||
        ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k')
      ) {
        event.preventDefault();
        if (localDrawingsRef.current.length) setSidebarOpen(true);
        else inputRef.current?.click();
      }
      if (ifcActive) return;
      if (event.key === '+' || event.key === '=')
        setZoom((value) => clampZoom(value + 0.15));
      if (event.key === '-') setZoom((value) => clampZoom(value - 0.15));
      if (event.key === '0') resetViewport();
      if (event.key.toLowerCase() === 'r')
        setRotation((value) => (value + 90) % 360);
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [ifcActive]);

  function resetViewport() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setRotation(0);
  }

  function pointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || (event.target as Element).closest('button'))
      return;
    dragRef.current = { x: event.clientX, y: event.clientY, pan };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  }
  function pointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.pan.x + event.clientX - dragRef.current.x,
      y: dragRef.current.pan.y + event.clientY - dragRef.current.y,
    });
  }
  function pointerUp() {
    dragRef.current = null;
    setDragging(false);
  }

  function updateLocalDrawings(next: LocalSource[]) {
    localDrawingsRef.current = next;
    setLocalDrawings(next);
  }

  function cancelPagePreview() {
    pageRef.current?.abort();
    pageRef.current = null;
    setPageLoading(false);
  }

  function chooseImported(source: LocalSource, closePicker = true) {
    viewVersion.current += 1;
    cancelPagePreview();
    activeImportIdRef.current = source.id;
    setActiveImportId(source.id);
    if (source.kind === 'ifc') setIfcEpoch((epoch) => epoch + 1);
    setInspectorOpen(true);
    if (closePicker) setSidebarOpen(false);
    resetViewport();
  }

  const updateIfcStatus = useCallback(
    (id: string, status: IfcStatus, error?: string) => {
      if (
        !localDrawingsRef.current.some(
          (source) =>
            source.id === id &&
            source.kind === 'ifc' &&
            (source.status !== status || source.error !== error),
        )
      )
        return;
      updateLocalDrawings(
        localDrawingsRef.current.map((source) =>
          source.id === id && source.kind === 'ifc'
            ? { ...source, status, error }
            : source,
        ),
      );
    },
    [],
  );

  async function openFiles(files: File[]) {
    if (!files.length) return;
    if (batchRef.current) {
      setToast('Please wait for the current import to finish.');
      return;
    }
    const controller = new AbortController();
    batchRef.current = controller;
    const version = viewVersion.current;
    const errors: ImportError[] = [];
    let lastSource: LocalSource | null = null;
    let count = 0;
    setSearch('');
    setImportErrors([]);
    try {
      // Decode one file at a time to limit simultaneous PDF/image allocations.
      for (const [index, file] of files.entries()) {
        setImportProgress({
          name: file.name,
          current: index + 1,
          total: files.length,
        });
        try {
          const preview = await importSource(
            file,
            `local-${++localId.current}`,
            controller.signal,
          );
          if (controller.signal.aborted) {
            releaseSource(preview);
            return;
          }
          lastSource = preview;
          updateLocalDrawings([...localDrawingsRef.current, lastSource]);
          count += 1;
        } catch (error) {
          if (controller.signal.aborted) return;
          errors.push({
            name: file.name,
            message:
              error instanceof Error
                ? error.message
                : 'This file could not be opened.',
          });
          setImportErrors([...errors]);
        }
      }
      // A source picked while a batch decodes keeps the user's selection.
      if (
        lastSource &&
        (version === viewVersion.current ||
          activeImportIdRef.current === null) &&
        localDrawingsRef.current.some((source) => source.id === lastSource?.id)
      )
        chooseImported(lastSource);
      if (errors.length && count) {
        setToast(
          `${count} imported; ${errors.length} could not be opened. See Drawings for details.`,
        );
      } else if (count) {
        setToast(
          `${count} ${count === 1 ? 'drawing' : 'drawings'} imported locally.`,
        );
      } else if (activeImportIdRef.current !== null) {
        setSidebarOpen(true);
      }
    } finally {
      if (batchRef.current === controller) {
        batchRef.current = null;
        setImportProgress(null);
      }
    }
  }

  async function openPage(source: LocalDrawing, page: number) {
    cancelPagePreview();
    const controller = new AbortController();
    pageRef.current = controller;
    const version = viewVersion.current;
    setPageLoading(true);
    try {
      const preview = await importDocument(
        source.file,
        page,
        controller.signal,
      );
      if (controller.signal.aborted || version !== viewVersion.current) {
        releaseDrawing(preview);
        return;
      }
      updateLocalDrawings(
        localDrawingsRef.current.map((item) =>
          item.id === source.id ? { ...preview, id: source.id } : item,
        ),
      );
      releaseDrawing(source);
      resetViewport();
    } catch (error) {
      if (!controller.signal.aborted)
        setToast(
          error instanceof Error
            ? error.message
            : 'This page could not be opened.',
        );
    } finally {
      if (pageRef.current === controller) {
        pageRef.current = null;
        setPageLoading(false);
      }
    }
  }

  function removeImported(source: LocalSource) {
    const index = localDrawingsRef.current.findIndex(
      (item) => item.id === source.id,
    );
    const next = localDrawingsRef.current.filter(
      (item) => item.id !== source.id,
    );
    if (source.id === activeImportId) {
      if (next.length)
        chooseImported(next[Math.min(index, next.length - 1)], false);
      else {
        viewVersion.current += 1;
        cancelPagePreview();
        activeImportIdRef.current = null;
        setActiveImportId(null);
        setInspectorOpen(false);
        setSidebarOpen(false);
        setSearch('');
        setImportErrors([]);
        resetViewport();
      }
    }
    updateLocalDrawings(next);
    releaseSource(source);
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    void openFiles(Array.from(event.target.files ?? []));
    event.target.value = '';
  }

  function fileDrag(
    event: ReactDragEvent,
    action: 'enter' | 'leave' | 'over' | 'drop',
  ) {
    if (!event.dataTransfer.types.includes('Files')) return;
    event.preventDefault();
    if (action === 'enter') {
      fileDragDepth.current += 1;
      setFileDragging(true);
    } else if (action === 'leave') {
      fileDragDepth.current = Math.max(0, fileDragDepth.current - 1);
      if (!fileDragDepth.current) setFileDragging(false);
    } else if (action === 'over') {
      event.dataTransfer.dropEffect = 'copy';
    } else {
      fileDragDepth.current = 0;
      setFileDragging(false);
      void openFiles(Array.from(event.dataTransfer.files));
    }
  }

  async function exportDrawing() {
    const svg = svgRef.current?.cloneNode(true) as SVGSVGElement | undefined;
    if (!svg || !imported) return;
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    svg.setAttribute('width', '1100');
    svg.setAttribute('height', '780');
    if (imported.url.startsWith('blob:')) {
      // PDF previews are rendered PNG blobs, not the original PDF bytes.
      const preview = await fetch(imported.url).then((result) => result.blob());
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = reject;
        reader.readAsDataURL(preview);
      });
      svg.querySelector('image')?.setAttribute('href', data);
    }
    downloadBlob(
      new Blob([new XMLSerializer().serializeToString(svg)], {
        type: 'image/svg+xml',
      }),
      `${imported.file.name}-preview.svg`,
    );
    setToast('Drawing exported.');
  }

  const visibleImports = localDrawings.filter((source) =>
    source.file.name.toLowerCase().includes(search.toLowerCase()),
  );
  // A native modal makes nodes outside it inert, including file inputs.
  const localFileInput = (
    <input
      ref={inputRef}
      className="visually-hidden"
      type="file"
      accept={SOURCE_ACCEPT}
      multiple
      tabIndex={-1}
      aria-label="Open local drawing"
      onChange={handleFile}
    />
  );

  return (
    <div
      className={`app-shell ${!hasDrawing ? 'awaiting-import' : ''}`}
      onDragEnter={(event) => fileDrag(event, 'enter')}
      onDragLeave={(event) => fileDrag(event, 'leave')}
      onDragOver={(event) => fileDrag(event, 'over')}
      onDrop={(event) => fileDrag(event, 'drop')}
    >
      <header className="topbar">
        <div className="topbar-brand">
          <Brand />
        </div>
        {hasDrawing && (
          <>
            <span className="topbar-divider" />
            <button
              className="file-picker-button"
              aria-label="Choose a drawing"
              aria-haspopup="dialog"
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen(true)}
            >
              <FolderOpen size={16} />
              <span>{t.drawings}</span>
              <span className="file-count">{localDrawings.length}</span>
              <ChevronDown size={13} />
            </button>
            <button
              className="secondary-button import-button"
              onClick={() => inputRef.current?.click()}
              disabled={importProgress !== null}
              aria-label={t.import}
              title={t.import}
            >
              <Upload size={15} />
              <span>{t.import}</span>
            </button>
          </>
        )}
        <div className="topbar-actions">
          {hasDrawing && (
            <span className="local-badge">
              <span />
              {t.local}
            </span>
          )}
          <button
            className="language-button"
            onClick={() => setLanguage(language === 'en' ? 'fi' : 'en')}
            title="Switch language / Vaihda kieli"
          >
            {language.toUpperCase()}
            <ChevronDown size={12} />
          </button>
          <span className="topbar-divider" />
          <button
            className="icon-button"
            aria-label={t.help}
            onClick={() => setHelpOpen(true)}
          >
            <CircleHelp size={18} />
          </button>
        </div>
      </header>

      {sidebarOpen && (
        <dialog
          className={`source-sidebar ${fileDragging ? 'file-drop-active' : ''}`}
          ref={drawingDialogRef}
          aria-labelledby="drawing-picker-title"
          onCancel={() => setSidebarOpen(false)}
          onClick={(event) => {
            if (event.target === drawingDialogRef.current) {
              const rect = event.currentTarget.getBoundingClientRect();
              if (
                event.clientX < rect.left ||
                event.clientX > rect.right ||
                event.clientY < rect.top ||
                event.clientY > rect.bottom
              )
                setSidebarOpen(false);
            }
          }}
        >
          {localFileInput}
          <div className="sidebar-section-title">
            <span id="drawing-picker-title">{t.drawings}</span>
            <button
              className="icon-button"
              aria-label="Close drawings"
              onClick={() => setSidebarOpen(false)}
            >
              <X size={18} />
            </button>
          </div>
          <p className="picker-description">{t.localFiles}</p>
          <button
            className="import-dropzone"
            onClick={() => inputRef.current?.click()}
            disabled={importProgress !== null}
          >
            <Upload size={21} />
            <strong>{fileDragging ? t.dropTitle : t.import}</strong>
            <span>
              {t.select} {t.drop}
            </span>
            <small>
              {t.formats}
            </small>
          </button>
          <p className="import-local-note">{t.localNote}</p>
          {importProgress && (
            <div className="import-progress" role="status">
              <span className="spinner" />
              <span>
                {importProgress.current} / {importProgress.total} ·{' '}
                {importProgress.name}
              </span>
            </div>
          )}
          <ImportErrors
            errors={importErrors}
            language={language}
            onDismiss={() => setImportErrors([])}
          />
          <label className="drawing-search">
            <Search size={14} />
            <input
              ref={searchRef}
              aria-label="Find a drawing"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.search}
            />
            <kbd>Esc</kbd>
          </label>
          <div className="source-group-label">
            <FileImage size={13} />
            {t.localFiles}
            <span>{localDrawings.length}</span>
          </div>
          <ImportedDrawingList
            drawings={visibleImports}
            activeId={activeImportId}
            language={language}
            onSelect={chooseImported}
            onRemove={removeImported}
          />
          {!visibleImports.length && (
            <p className="search-empty">
              {language === 'fi'
                ? 'Piirustuksia ei löytynyt.'
                : `No drawings match “${search}”.`}
            </p>
          )}
        </dialog>
      )}

      {!activeSource ? (
        <main className="import-screen">
          <div className="import-welcome">
            <span className="eyebrow">
              {language === 'fi' ? 'OMA TYÖTILASI' : 'YOUR WORKSPACE'}
            </span>
            <h1>{t.welcome}</h1>
            <p className="import-intro">{t.welcomeIntro}</p>
            <button
              className={`welcome-dropzone ${fileDragging ? 'file-drop-active' : ''}`}
              onClick={() => inputRef.current?.click()}
              disabled={importProgress !== null}
              aria-label={t.select}
              aria-describedby="import-formats import-privacy"
              aria-busy={importProgress !== null}
            >
              <span className="welcome-upload-icon">
                {importProgress ? (
                  <span className="spinner" />
                ) : (
                  <Upload size={28} strokeWidth={1.5} />
                )}
              </span>
              <strong>
                {importProgress
                  ? t.opening
                  : fileDragging
                    ? t.dropTitle
                    : t.select}
              </strong>
              <span className="welcome-drop-hint">
                {importProgress
                  ? `${importProgress.current} / ${importProgress.total} · ${importProgress.name}`
                  : t.drop}
              </span>
              <span className="welcome-formats" id="import-formats">
                {t.formats}
              </span>
            </button>
            {importProgress && (
              <p className="visually-hidden" role="status">
                {t.opening} {importProgress.name}
              </p>
            )}
            {!sidebarOpen && (
              <ImportErrors
                errors={importErrors}
                language={language}
                onDismiss={() => setImportErrors([])}
              />
            )}
            <p className="welcome-privacy" id="import-privacy">
              {t.localNote}
            </p>
          </div>
          <span className="import-screen-footnote">{SOURCE_FORMATS}</span>
        </main>
      ) : (
        <div
          className={`app-body ${!inspectorOpen ? 'inspector-collapsed' : ''}`}
        >
          <main className="workspace">
            <div className="workspace-heading">
              <div>
                <div className="eyebrow">
                  <span className="sheet-index">{t.local}</span>
                  <span>
                    {ifcSource
                      ? language === 'fi'
                        ? 'TUOTU IFC-MALLI'
                        : 'IMPORTED IFC MODEL'
                      : language === 'fi'
                        ? 'TUOTU PIIRUSTUS'
                        : 'IMPORTED DRAWING'}
                  </span>
                </div>
                <div className="drawing-title">
                  <h1 title={title}>{title}</h1>
                </div>
              </div>
              <div className="workspace-heading-actions">
                <span className="revision-tag">
                  {ifcSource
                    ? 'IFC · 3D'
                    : imported?.kind === 'pdf'
                      ? 'PDF'
                      : activeSource.file.name.split('.').pop()?.toUpperCase()}
                </span>
                {!ifcSource && (
                  <button
                    className="secondary-button export-button"
                    onClick={() =>
                      void exportDrawing().catch(() =>
                        setToast(
                          'This drawing could not be exported. Please try again.',
                        ),
                      )
                    }
                  >
                    <ArrowDownToLine size={14} />
                    {t.export}
                  </button>
                )}
              </div>
            </div>
            <div className="viewer-shell">
              {ifcSource ? (
                <ViewerBoundary
                  key={`${ifcSource.id}:${ifcEpoch}`}
                  onBrowse={() => setSidebarOpen(true)}
                >
                  <Suspense
                    fallback={
                      <div className="ifc-module-loading" role="status">
                        <span className="spinner" />
                        Loading 3D viewer…
                      </div>
                    }
                  >
                    <IfcWorkbench
                      key={`${ifcSource.id}:${ifcEpoch}`}
                      source={ifcSource}
                      inspectorContainer={ifcInspectorHost}
                      inspectorOpen={inspectorOpen}
                      toggleInspector={() => setInspectorOpen((open) => !open)}
                      onStatus={updateIfcStatus}
                      onRemove={() => removeImported(ifcSource)}
                    />
                  </Suspense>
                </ViewerBoundary>
              ) : imported ? (
                <>
                  <div className="viewer-toolbar">
                    <div className="view-mode">
                      <span className="view-mode-icon">
                        <LayoutGrid size={13} />
                      </span>
                      {language === 'fi' ? '2D-piirustus' : '2D drawing'}
                    </div>
                    <span className="viewer-separator" />
                    <span className="scope-indicator">
                      <FileText size={12} />
                      {t.current}
                    </span>
                    <div className="viewer-tools">
                      <button
                        className="icon-button"
                        aria-label="Toggle chat panel"
                        title={t.ask}
                        aria-expanded={inspectorOpen}
                        aria-controls="answer-panel"
                        onClick={() => setInspectorOpen(!inspectorOpen)}
                      >
                        <PanelRightClose size={17} />
                      </button>
                    </div>
                  </div>
                  <div
                    ref={stageRef}
                    className={`drawing-stage ${dragging ? 'is-dragging' : ''}`}
                    onPointerDown={pointerDown}
                    onPointerMove={pointerMove}
                    onPointerUp={pointerUp}
                    onPointerCancel={pointerUp}
                    onDoubleClick={resetViewport}
                  >
                    <div
                      className="source-sheet"
                      style={{
                        width: paperWidth,
                        height: (paperWidth * 780) / 1100,
                        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom}) rotate(${rotation}deg)`,
                      }}
                    >
                      <svg
                        ref={svgRef}
                        viewBox="0 0 1100 780"
                        xmlns="http://www.w3.org/2000/svg"
                        aria-label={`${imported.file.name} source drawing`}
                      >
                        <image
                          href={imported.url}
                          x="25"
                          y="25"
                          width="1050"
                          height="730"
                          preserveAspectRatio="xMidYMid meet"
                        />
                      </svg>
                    </div>
                    <div className="stage-corner">
                      <MousePointer2 size={12} />
                      {dragging
                        ? 'Panning drawing'
                        : 'Drag to pan · Scroll to zoom · Drop files to import'}
                    </div>
                    {importing && (
                      <div className="viewer-loading" role="status">
                        <span className="spinner" />
                        {importProgress
                          ? `${language === 'fi' ? 'Tuodaan' : 'Importing'} ${importProgress.current} / ${importProgress.total} · ${importProgress.name}`
                          : language === 'fi'
                            ? 'Avataan PDF-sivua…'
                            : 'Opening PDF page…'}
                      </div>
                    )}
                    <div className="zoom-controls">
                      <button
                        className="icon-button"
                        aria-label="Zoom out"
                        onClick={() => setZoom((value) => clampZoom(value - 0.15))}
                      >
                        <Minus size={16} />
                      </button>
                      <button
                        className="zoom-value"
                        aria-label="Reset zoom"
                        onClick={resetViewport}
                      >
                        {Math.round(zoom * 100)}%
                      </button>
                      <button
                        className="icon-button"
                        aria-label="Zoom in"
                        onClick={() => setZoom((value) => clampZoom(value + 0.15))}
                      >
                        <Plus size={16} />
                      </button>
                      <span />
                      <button
                        className="icon-button"
                        aria-label="Rotate drawing"
                        title="Rotate · R"
                        onClick={() => setRotation((value) => (value + 90) % 360)}
                      >
                        <RotateCw size={16} />
                      </button>
                      <button
                        className="icon-button"
                        aria-label="Fit drawing"
                        title="Fit drawing · 0"
                        onClick={resetViewport}
                      >
                        <Expand size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="viewer-footer">
                    <span>
                      <FileText size={12} />
                      {imported.file.name}
                    </span>
                    <div className="page-navigation">
                      <button
                        className="icon-button"
                        aria-label="Previous PDF page"
                        disabled={importing || imported.page === 1}
                        onClick={() => void openPage(imported, imported.page - 1)}
                      >
                        <ChevronLeft size={14} />
                      </button>
                      <span>
                        {imported.page} / {imported.pages}
                      </span>
                      <button
                        className="icon-button"
                        aria-label="Next PDF page"
                        disabled={importing || imported.page >= imported.pages}
                        onClick={() => void openPage(imported, imported.page + 1)}
                      >
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </>
              ) : null}
            </div>
            <div className="workspace-footnote">
              <span className="footnote-icon">
                <Check size={13} />
              </span>
              {ifcSource ? 'Local 3D inspection · source properties only' : t.only}
              {!ifcSource && (
                <span className="footnote-shortcut">
                  <kbd>0</kbd> Fit <span>·</span> <kbd>R</kbd> Rotate
                </span>
              )}
            </div>
          </main>
          {inspectorOpen &&
            (ifcSource ? (
              <div
                className="answer-panel"
                id="model-inspector"
                role="complementary"
                aria-label="Model inspector"
                ref={setIfcInspectorHost}
              />
            ) : imported ? (
              <aside
                className="answer-panel"
                id="answer-panel"
                aria-label="Drawing chat"
              >
                <div className="answer-panel-header">
                  <span className="ask-icon">
                    <Sparkles size={19} strokeWidth={1.7} />
                  </span>
                  <div>
                    <h2>{t.ask}</h2>
                    <p>{t.intro}</p>
                  </div>
                  <button
                    className="icon-button panel-close"
                    aria-label="Close chat panel"
                    onClick={() => setInspectorOpen(false)}
                  >
                    <PanelRightClose size={17} />
                  </button>
                </div>
                <div className="local-preview-state">
                  <span className="empty-state-icon">
                    <FileImage size={28} />
                  </span>
                  <h3>
                    {language === 'fi'
                      ? 'Piirustuksesi on valmis katseltavaksi.'
                      : 'Your drawing is ready to view.'}
                  </h3>
                  <p>
                    {language === 'fi'
                      ? 'Siirrä, suurenna, kierrä tai selaa PDF-sivuja. Tiedostosi pysyy tässä välilehdessä.'
                      : 'Pan, zoom, rotate, or browse PDF pages. Your file stays in this tab.'}
                  </p>
                  <div className="chat-file-card">
                    {imported.kind === 'pdf' ? (
                      <FileText size={20} />
                    ) : (
                      <FileImage size={20} />
                    )}
                    <div>
                      <strong title={imported.file.name}>
                        {imported.file.name}
                      </strong>
                      <span className="local-file-details">
                        {fileSize(imported.file.size)} ·{' '}
                        {imported.kind === 'pdf'
                          ? `${imported.pages} ${language === 'fi' ? 'sivua' : imported.pages === 1 ? 'page' : 'pages'}`
                          : `${imported.width} × ${imported.height} px`}
                      </span>
                    </div>
                    <Check size={14} />
                  </div>
                </div>
                <div className="question-section">
                  <p className="chat-availability" id="chat-availability">
                    {t.chatUnavailable}
                  </p>
                  <div className="question-scope">
                    <FileText size={12} />
                    <span>{imported.file.name}</span>
                    <span className="scope-lock">
                      <Check size={11} />
                      {language === 'fi' ? 'Vain tämä näkymä' : 'This view only'}
                    </span>
                  </div>
                  <form
                    className="question-form"
                    onSubmit={(event) => event.preventDefault()}
                  >
                    <textarea
                      aria-label="Question about the drawing"
                      aria-describedby="chat-availability"
                      placeholder={t.placeholder}
                      disabled
                      rows={2}
                    />
                    <div className="question-form-footer">
                      <span>{t.local}</span>
                      <button
                        type="submit"
                        className="ask-submit"
                        aria-label={t.askButton}
                        disabled
                      >
                        <ArrowUp size={17} />
                      </button>
                    </div>
                  </form>
                </div>
              </aside>
            ) : null)}
        </div>
      )}
      {!sidebarOpen && localFileInput}
      {fileDragging && hasDrawing && !sidebarOpen && (
        <div className="file-drop-overlay" role="status">
          <Upload size={38} />
          <strong>{t.dropTitle}</strong>
          <span>{SOURCE_FORMATS}</span>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setToast('')}
          >
            <X size={14} />
          </button>
        </div>
      )}
      {helpOpen && <HelpDialog onClose={() => setHelpOpen(false)} />}
    </div>
  );
}
