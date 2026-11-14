import { useEffect, useRef, useState } from 'react';
import type {
  ChangeEvent,
  DragEvent as ReactDragEvent,
  FormEvent,
  PointerEvent as ReactPointerEvent,
} from 'react';
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Building2,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  CircleAlert,
  Clock3,
  Expand,
  Eye,
  EyeOff,
  FileImage,
  FileText,
  FolderOpen,
  Layers2,
  LayoutGrid,
  Maximize,
  Minus,
  MousePointer2,
  PanelRightClose,
  Plus,
  RotateCw,
  ScanLine,
  Search,
  Sparkles,
  SquareDashedMousePointer,
  Tag,
  Upload,
  X,
} from 'lucide-react';
import { DrawingArtwork } from './components/DrawingArtwork';
import { MarkLayer } from './components/MarkLayer';
import { CandidateLayer } from './components/CandidateLayer';
import { CandidatePanel } from './components/CandidatePanel';
import type { ImageCandidateResponse } from './contracts/ImageCandidateResponse';
import { prepareCandidateImage, requestCandidates } from './lib/candidateApi';
import { candidateBounds } from './lib/candidateGeometry';
import {
  ImportedDrawingList,
  fileSize,
} from './components/ImportedDrawingList';
import { DRAWINGS, suggestions } from './demo/data';
import { askDemo, resolveDemo } from './demo/engine';
import { areaPath, clampZoom, focusPan } from './lib/viewport';
import {
  importDocument,
  IMPORT_ACCEPT,
  IMPORT_FORMATS,
  releaseDrawing,
} from './lib/importDocument';
import type {
  DemoResponse,
  Drawing,
  Language,
  LocalDrawing,
  Mark,
} from './types';

const initialQuestion = 'How many doors are shown?';
const copy = {
  en: {
    drawings: 'Drawings',
    search: 'Find a drawing…',
    source: 'Source drawings',
    add: 'Add drawing',
    current: 'Current drawing',
    ask: 'Ask the drawing',
    intro: 'Every answer, grounded in the drawing.',
    placeholder: 'What would you like to know?',
    askButton: 'Ask question',
    try: 'QUICK QUESTIONS',
    answer: 'ANSWER',
    objects: 'Evidence',
    calculation: 'Calculation',
    shown: 'shown in this view',
    only: 'Based only on the selected drawing',
    complete: 'All matches located',
    empty: 'Nothing is selected',
    project: 'West Harbour Residence',
    demonstration: 'Demo data',
    export: 'Export',
    open: 'Open a drawing',
    latest: 'LATEST QUESTION',
    local: 'Your drawing',
    noEvidence: 'No source evidence for this answer',
    help: 'How it works',
    revision: 'Revision',
    import: 'Import drawings',
    drop: 'Choose files or drop them here',
    localFiles: 'Your imports',
    localNote: 'Imports last until refresh. Asking sends the displayed image to Nemotron.',
    dropTitle: 'Drop drawings to import',
    importErrors: 'Some files could not be opened',
  },
  fi: {
    drawings: 'Piirustukset',
    search: 'Etsi piirustusta…',
    source: 'Lähdepiirustukset',
    add: 'Lisää piirustus',
    current: 'Valittu piirustus',
    ask: 'Kysy piirustukselta',
    intro: 'Jokainen vastaus suoraan piirustuksesta.',
    placeholder: 'Mitä haluat tietää?',
    askButton: 'Kysy',
    try: 'KOKEILE KYSYMYSTÄ',
    answer: 'VASTAUS',
    objects: 'Lähteet',
    calculation: 'Laskenta',
    shown: 'näkyy tässä näkymässä',
    only: 'Perustuu vain valittuun piirustukseen',
    complete: 'Kaikki kohteet paikannettu',
    empty: 'Kohdetta ei ole valittu',
    project: 'West Harbour Residence',
    demonstration: 'Demotiedot',
    export: 'Vie',
    open: 'Avaa piirustus',
    latest: 'VIIMEISIN KYSYMYS',
    local: 'Oma piirustus',
    noEvidence: 'Vastausta ei voida perustella lähteellä',
    help: 'Miten tämä toimii',
    revision: 'Versio',
    import: 'Tuo piirustuksia',
    drop: 'Valitse tiedostot tai pudota ne tähän',
    localFiles: 'Omat tiedostot',
    localNote:
      'Tuonnit säilyvät sivun päivittämiseen asti. Kysymys lähettää näkyvän kuvan Nemotronille.',
    dropTitle: 'Pudota tuotavat piirustukset',
    importErrors: 'Joitakin tiedostoja ei voitu avata',
  },
};

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand">
      <span className="brand-mark">
        <ScanLine size={20} strokeWidth={1.7} />
      </span>
      {!compact && (
        <span className="brand-wordmark">
          ask<span className="brand-light">the</span>plan
        </span>
      )}
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
      onClick={(e) => {
        if (e.target === ref.current) onClose();
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
        <SquareDashedMousePointer size={25} />
      </span>
      <h2>From question to evidence.</h2>
      <p>
        Choose a drawing, ask a question, and explore the answer on the source.
        Select a numbered mark or evidence row to inspect it.
      </p>
      <div className="help-note">
        <Sparkles size={17} />
        <span>
          Demo drawings use prepared answers. Import your own drawing and ask
          a question to locate candidates with Nemotron. Submitting a question
          sends the displayed image or PDF page to the analysis service.
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
        <span>Toggle markings</span>
        <kbd>O</kbd>
        <span>Clear selection</span>
        <kbd>Esc</kbd>
      </div>
      <button className="primary-button" onClick={onClose}>
        Explore the drawing <ArrowRight size={16} />
      </button>
    </dialog>
  );
}

function SourceContext({
  drawing,
  mark,
  onFocus,
  language,
}: {
  drawing: Drawing;
  mark: Mark;
  onFocus: () => void;
  language: Language;
}) {
  const [x, y, width, height] = mark.bounds;
  const cropWidth = Math.min(1100, Math.max(240, width + 120));
  const cropHeight = Math.min(780, Math.max(height + 80, cropWidth * 0.47));
  const cropX = Math.max(
    0,
    Math.min(1100 - cropWidth, x + width / 2 - cropWidth / 2),
  );
  const cropY = Math.max(
    0,
    Math.min(780 - cropHeight, y + height / 2 - cropHeight / 2),
  );
  return (
    <section
      className="source-context"
      aria-label={
        language === 'fi' ? 'Valitun kohteen lähde' : 'Selected source context'
      }
    >
      <div className="context-heading">
        <span>
          <ScanLine size={13} />
          {language === 'fi' ? 'VALITTU KOHDE' : 'SOURCE CLOSE-UP'}
        </span>
        <span>
          {drawing.code} · {mark.label}
        </span>
      </div>
      <button
        className="context-preview"
        onClick={onFocus}
        aria-label={`Focus ${mark.label} on the drawing`}
      >
        <svg
          viewBox={`${cropX} ${cropY} ${cropWidth} ${cropHeight}`}
          aria-hidden="true"
        >
          <DrawingArtwork drawing={drawing} />
          {mark.kind === 'area' && mark.polygon ? (
            <path
              d={areaPath(mark.polygon, mark.holes)}
              fillRule="evenodd"
              fill="var(--accent)"
              fillOpacity="0.08"
              stroke="var(--accent)"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
          ) : (
            <rect
              x={x}
              y={y}
              width={width}
              height={height}
              rx="3"
              fill="var(--accent)"
              fillOpacity="0.08"
              stroke="var(--accent)"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
        <span className="context-focus">
          <Maximize size={13} />
          {language === 'fi' ? 'Näytä piirustuksessa' : 'Focus on drawing'}
        </span>
      </button>
      <div className="context-caption">
        <strong>{mark.label}</strong>
        <span>{mark.detail}</span>
      </div>
    </section>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function App() {
  const [language, setLanguage] = useState<Language>('en');
  const t = copy[language];
  const [drawingId, setDrawingId] = useState('ground');
  const drawing = DRAWINGS.find((d) => d.id === drawingId)!;
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<DemoResponse | null>(() =>
    resolveDemo(DRAWINGS[0], initialQuestion, 'en'),
  );
  const [candidateResponse, setCandidateResponse] = useState<{
    result: ImageCandidateResponse;
    question: string;
  } | null>(null);
  const [candidateError, setCandidateError] = useState('');
  const [analysisUrl, setAnalysisUrl] = useState<string | null>(null);
  const analysisUrlRef = useRef<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'evidence' | 'calculation'>(
    'evidence',
  );
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [paperWidth, setPaperWidth] = useState(800);
  const [showMarks, setShowMarks] = useState(true);
  const [showLabels, setShowLabels] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [helpOpen, setHelpOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [localDrawings, setLocalDrawings] = useState<LocalDrawing[]>([]);
  const [activeImportId, setActiveImportId] = useState<string | null>(null);
  const imported =
    localDrawings.find((source) => source.id === activeImportId) ?? null;
  const localActive = imported !== null;
  const displayImported = imported && analysisUrl ? { ...imported, url: analysisUrl } : imported;
  const [importProgress, setImportProgress] = useState<{
    name: string;
    current: number;
    total: number;
  } | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const importing = importProgress !== null || pageLoading;
  const [importErrors, setImportErrors] = useState<
    { name: string; message: string }[]
  >([]);
  const [fileDragging, setFileDragging] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const drawingDialogRef = useRef<HTMLDialogElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const viewVersion = useRef(0);
  const localDrawingsRef = useRef<LocalDrawing[]>([]);
  const batchRef = useRef<AbortController | null>(null);
  const pageRef = useRef<AbortController | null>(null);
  const fileDragDepth = useRef(0);
  const localId = useRef(0);
  const dragRef = useRef<{
    x: number;
    y: number;
    pan: { x: number; y: number };
  } | null>(null);
  const title =
    localActive && imported
      ? imported.file.name
      : language === 'fi'
        ? drawing.titleFi
        : drawing.title;
  const marks = localActive ? [] : (response?.marks ?? []);
  const candidateCount = localActive ? (candidateResponse?.result.candidates?.length ?? 0) : 0;
  const overlayCount = localActive ? candidateCount : marks.length;
  const selectedMark = marks.find((mark) => mark.id === selected);
  const missing = response?.intent === 'missing';

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
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
      setZoom((z) => clampZoom(z * Math.exp(-event.deltaY * 0.001)));
    };
    stage.addEventListener('wheel', wheel, { passive: false });
    return () => {
      observer.disconnect();
      stage.removeEventListener('wheel', wheel);
    };
  }, [inspectorOpen]);
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
      requestRef.current?.abort();
      batchRef.current?.abort();
      batchRef.current = null;
      pageRef.current?.abort();
      pageRef.current = null;
      localDrawingsRef.current.forEach(releaseDrawing);
      localDrawingsRef.current = [];
      if (analysisUrlRef.current) URL.revokeObjectURL(analysisUrlRef.current);
    },
    [],
  );
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelected(null);
        setLayersOpen(false);
        setExportOpen(false);
        setSidebarOpen(false);
      }
      if ((event.target as HTMLElement).closest('input, textarea, dialog'))
        return;
      if (
        event.key === '/' ||
        ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k')
      ) {
        event.preventDefault();
        setSidebarOpen(true);
      }
      if (event.key === '+' || event.key === '=')
        setZoom((z) => clampZoom(z + 0.15));
      if (event.key === '-') setZoom((z) => clampZoom(z - 0.15));
      if (event.key === '0') resetViewport();
      if (event.key.toLowerCase() === 'r') setRotation((r) => (r + 90) % 360);
      if (event.key.toLowerCase() === 'o') setShowMarks((s) => !s);
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);

  function resetViewport() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setRotation(0);
  }

  function clearCandidates() {
    setCandidateResponse(null);
    setCandidateError('');
    if (analysisUrlRef.current) URL.revokeObjectURL(analysisUrlRef.current);
    analysisUrlRef.current = null;
    setAnalysisUrl(null);
  }

  function chooseDrawing(next: Drawing) {
    clearCandidates();
    requestRef.current?.abort();
    requestRef.current = null;
    viewVersion.current += 1;
    cancelPagePreview();
    setDrawingId(next.id);
    setActiveImportId(null);
    setAsking(false);
    setSelected(null);
    setQuery('');
    setResponse(resolveDemo(next, suggestions(next, language)[0], language));
    setActiveTab('evidence');
    setSidebarOpen(false);
    setShowMarks(true);
    setLayersOpen(false);
    resetViewport();
  }

  async function ask(question: string) {
    if (!question.trim() || importing || asking) return;
    const questionText = question.trim();
    requestRef.current?.abort();
    clearCandidates();
    const controller = new AbortController();
    requestRef.current = controller;
    setAsking(true);
    setSelected(null);
    setActiveTab('evidence');
    setShowMarks(true);
    try {
      if (imported) {
        const image = await prepareCandidateImage(imported, controller.signal);
        if (requestRef.current !== controller || controller.signal.aborted) return;
        const snapshot = URL.createObjectURL(image.blob);
        analysisUrlRef.current = snapshot;
        setAnalysisUrl(snapshot);
        const answer = await requestCandidates(image, questionText, controller.signal);
        if (requestRef.current !== controller || controller.signal.aborted) return;
        setCandidateResponse({ result: answer, question: questionText });
      } else {
        const answer = await askDemo(drawing, questionText, language, controller.signal);
        if (requestRef.current !== controller || controller.signal.aborted) return;
        setResponse(answer);
      }
      setQuery('');
      setHistory((h) =>
        [questionText, ...h.filter((q) => q !== questionText)].slice(0, 4),
      );
      resetViewport();
    } catch (error) {
      if (requestRef.current === controller && !controller.signal.aborted) {
        if (imported) setCandidateError(error instanceof Error ? error.message : 'Candidate analysis failed. Please try again.');
        else setToast('The demo answer could not be loaded. Please try again.');
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setAsking(false);
      }
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(query);
  }

  function focusMark(mark: Mark) {
    setSelected(mark.id);
    setShowMarks(true);
    const nextZoom = mark.kind === 'area' ? 1.35 : 1.65;
    setZoom(nextZoom);
    setPan(focusPan(mark.bounds, paperWidth, nextZoom, rotation));
  }

  function focusCandidate(id: string) {
    const result = candidateResponse?.result;
    const candidate = result?.candidates?.find((item) => item.id === id);
    if (!result || !candidate) return;
    setSelected(id);
    setShowMarks(true);
    setZoom(1.65);
    setPan(focusPan(candidateBounds(candidate, result.image), paperWidth, 1.65, rotation));
  }

  function pointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (
      event.button !== 0 ||
      (event.target as Element).closest('.evidence-mark,.candidate-mark,button')
    )
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

  function updateLocalDrawings(next: LocalDrawing[]) {
    localDrawingsRef.current = next;
    setLocalDrawings(next);
  }

  function cancelPagePreview() {
    pageRef.current?.abort();
    pageRef.current = null;
    setPageLoading(false);
  }

  function chooseImported(source: LocalDrawing, closePicker = true) {
    clearCandidates();
    viewVersion.current += 1;
    cancelPagePreview();
    requestRef.current?.abort();
    requestRef.current = null;
    setAsking(false);
    setActiveImportId(source.id);
    setResponse(null);
    setSelected(null);
    setQuery('');
    setLayersOpen(false);
    setExportOpen(false);
    if (closePicker) setSidebarOpen(false);
    resetViewport();
  }

  async function openFiles(files: File[]) {
    if (!files.length) return;
    if (batchRef.current) {
      setToast('Please wait for the current import to finish.');
      return;
    }
    const controller = new AbortController();
    batchRef.current = controller;
    const version = viewVersion.current;
    const errors: { name: string; message: string }[] = [];
    let lastSource: LocalDrawing | null = null;
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
          const preview = await importDocument(file, 1, controller.signal);
          if (controller.signal.aborted) {
            releaseDrawing(preview);
            return;
          }
          lastSource = { ...preview, id: `local-${++localId.current}` };
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
        version === viewVersion.current &&
        localDrawingsRef.current.some((source) => source.id === lastSource?.id)
      )
        chooseImported(lastSource, !errors.length);
      if (errors.length) setSidebarOpen(true);
      setToast(
        errors.length
          ? `${count} imported; ${errors.length} could not be opened. See Drawings for details.`
          : `${count} ${count === 1 ? 'drawing' : 'drawings'} imported locally. Available in Drawings.`,
      );
    } finally {
      if (batchRef.current === controller) {
        batchRef.current = null;
        setImportProgress(null);
      }
    }
  }

  async function openPage(source: LocalDrawing, page: number) {
    requestRef.current?.abort();
    requestRef.current = null;
    setAsking(false);
    clearCandidates();
    setSelected(null);
    viewVersion.current += 1;
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

  function removeImported(source: LocalDrawing) {
    const index = localDrawingsRef.current.findIndex(
      (item) => item.id === source.id,
    );
    const next = localDrawingsRef.current.filter(
      (item) => item.id !== source.id,
    );
    if (source.id === activeImportId) {
      if (next.length)
        chooseImported(next[Math.min(index, next.length - 1)], false);
      else chooseDrawing(drawing);
    }
    updateLocalDrawings(next);
    releaseDrawing(source);
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    void openFiles(files);
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
    if (!svg) return;
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    svg.setAttribute('width', '1100');
    svg.setAttribute('height', '780');
    if (localActive && displayImported?.url.startsWith('blob:')) {
      // PDF previews are rendered PNG blobs, not the original PDF bytes.
      const preview = await fetch(displayImported.url).then((result) => result.blob());
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
      `${localActive ? 'local-drawing' : drawing.code}-marked.svg`,
    );
    setExportOpen(false);
    setToast('Marked drawing exported.');
  }

  function changeLanguage() {
    const next = language === 'en' ? 'fi' : 'en';
    setLanguage(next);
    if (response && !localActive)
      setResponse(resolveDemo(drawing, response.question, next));
  }

  const visibleDrawings = DRAWINGS.filter((d) =>
    `${d.title} ${d.titleFi} ${d.code}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const visibleImports = localDrawings.filter((source) =>
    source.file.name.toLowerCase().includes(search.toLowerCase()),
  );
  const chips = suggestions(drawing, language);
  const chipNames =
    drawing.kind === 'schedule'
      ? language === 'en'
        ? ['Door count', 'D03 width', 'Fire rating']
        : ['Ovien määrä', 'D03 leveys', 'Paloluokka']
      : drawing.kind === 'elevation'
        ? language === 'en'
          ? ['Windows', 'Doors']
          : ['Ikkunat', 'Ovet']
        : language === 'en'
          ? ['Doors', 'Windows', 'Room area', 'Corridor width']
          : ['Ovet', 'Ikkunat', 'Huoneen ala', 'Käytävän leveys'];
  // A native modal makes nodes outside it inert, including file inputs.
  const localFileInput = (
    <input
      ref={inputRef}
      className="visually-hidden"
      type="file"
      accept={IMPORT_ACCEPT}
      multiple
      tabIndex={-1}
      aria-label="Open local drawing"
      onChange={handleFile}
    />
  );

  return (
    <div
      className="app-shell"
      onDragEnter={(event) => fileDrag(event, 'enter')}
      onDragLeave={(event) => fileDrag(event, 'leave')}
      onDragOver={(event) => fileDrag(event, 'over')}
      onDrop={(event) => fileDrag(event, 'drop')}
    >
      <header className="topbar">
        <div className="topbar-brand">
          <Brand />
        </div>
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
          <span className="file-count">
            {DRAWINGS.length + localDrawings.length}
          </span>
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
        <div className="project-breadcrumb">
          <span className="breadcrumb-slash">/</span>
          {localActive ? <FileImage size={14} /> : <Building2 size={14} />}
          <span>{localActive ? t.localFiles : t.project}</span>
        </div>
        <div className="topbar-actions">
          <span className="demo-badge">
            <span />
            {localActive ? t.local : t.demonstration}
          </span>
          <button
            className="language-button"
            onClick={changeLanguage}
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

      <div
        className={`app-body ${!inspectorOpen ? 'inspector-collapsed' : ''}`}
      >
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
            <p className="picker-description">
              {language === 'fi'
                ? 'Demopiirustukset ja paikalliset tiedostot'
                : 'Demo drawings and local files'}
            </p>
            <button
              className="import-dropzone"
              onClick={() => inputRef.current?.click()}
              disabled={importProgress !== null}
            >
              <Upload size={21} />
              <strong>{fileDragging ? t.dropTitle : t.import}</strong>
              <span>{t.drop}</span>
              <small>
                {IMPORT_FORMATS} · 35 MB /{' '}
                {language === 'fi' ? 'tiedosto' : 'file'}
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
            {!!importErrors.length && (
              <section
                className="import-errors"
                role="alert"
                aria-label={t.importErrors}
              >
                <div>
                  <CircleAlert size={15} />
                  <strong>{t.importErrors}</strong>
                  <button
                    className="icon-button"
                    onClick={() => setImportErrors([])}
                    aria-label={
                      language === 'fi'
                        ? 'Sulje tuontivirheet'
                        : 'Dismiss import errors'
                    }
                  >
                    <X size={14} />
                  </button>
                </div>
                <ul>
                  {importErrors.map((error, index) => (
                    <li key={index}>
                      <strong>{error.name}</strong>
                      <span>{error.message}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <label className="drawing-search">
              <Search size={14} />
              <input
                ref={searchRef}
                aria-label="Find a drawing"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t.search}
              />
              <kbd>Esc</kbd>
            </label>
            {!!localDrawings.length && (
              <>
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
              </>
            )}
            <div
              className={`source-group-label ${localDrawings.length ? 'following-source-group' : ''}`}
            >
              <FolderOpen size={13} />
              {language === 'fi' ? 'Demopiirustukset' : 'Demo drawings'}
              <span>{DRAWINGS.length}</span>
            </div>
            <div className="drawing-list">
              {visibleDrawings.map((doc) => (
                <button
                  key={doc.id}
                  className={`drawing-card ${!localActive && drawing.id === doc.id ? 'active-drawing' : ''}`}
                  onClick={() => chooseDrawing(doc)}
                  aria-pressed={!localActive && drawing.id === doc.id}
                >
                  <span className="drawing-thumbnail">
                    <svg viewBox="0 0 1100 780">
                      <DrawingArtwork drawing={doc} miniature />
                    </svg>
                    <span>{doc.code}</span>
                  </span>
                  <span className="drawing-card-description">
                    <strong>
                      {language === 'fi' ? doc.titleFi : doc.title}
                    </strong>
                    <span>
                      {doc.code} <span className="tiny-dot">·</span> Rev.{' '}
                      {doc.revision}
                    </span>
                  </span>
                  {!localActive && drawing.id === doc.id && (
                    <span className="active-dot" />
                  )}
                </button>
              ))}
              {!visibleDrawings.length && !visibleImports.length && (
                <p className="search-empty">No drawings match “{search}”.</p>
              )}
            </div>
            <div className="sidebar-footer">
              <FileText size={14} />
              <span>
                {language === 'fi'
                  ? 'Havainnollistavat lähdepiirustukset'
                  : 'Illustrative source drawings'}
              </span>
              <button
                className="icon-button"
                aria-label="Workspace information"
                onClick={() => setHelpOpen(true)}
              >
                <CircleHelp size={15} />
              </button>
            </div>
          </dialog>
        )}

        <main className="workspace">
          <div className="workspace-heading">
            <div>
              <div className="eyebrow">
                <span className="sheet-index">
                  {localActive ? t.local : drawing.code}
                </span>
                <span>
                  {localActive
                    ? language === 'fi'
                      ? 'TUOTU PIIRUSTUS'
                      : 'IMPORTED DRAWING'
                    : language === 'fi'
                      ? 'ARKKITEHTUURI'
                      : 'ARCHITECTURE'}
                </span>
              </div>
              <div className="drawing-title">
                <h1 title={title}>{title}</h1>
                <span>{localActive ? 'LOCAL' : drawing.level}</span>
              </div>
            </div>
            <div className="workspace-heading-actions">
              <span className="revision-tag">
                {localActive
                  ? imported?.kind === 'pdf'
                    ? 'PDF'
                    : imported?.file.name.split('.').pop()?.toUpperCase()
                  : `Rev. ${drawing.revision}`}
              </span>
              <div className="export-wrap">
                <button
                  className="secondary-button export-button"
                  onClick={() => setExportOpen(!exportOpen)}
                >
                  <ArrowDownToLine size={14} />
                  {t.export}
                  <ChevronDown size={12} />
                </button>
                {exportOpen && (
                  <div className="popover export-popover">
                    <button
                      onClick={() =>
                        void exportDrawing().catch(() =>
                          setToast(
                            'This drawing could not be exported. Please try again.',
                          ),
                        )
                      }
                    >
                      <FileImage size={15} />
                      Marked drawing <span>.svg</span>
                    </button>
                    <button
                      disabled={localActive ? !candidateResponse : !response}
                      onClick={() => {
                        if (candidateResponse && localActive)
                          downloadBlob(new Blob([JSON.stringify(candidateResponse.result, null, 2)], { type: 'application/json' }), 'drawing-candidates.json');
                        else if (response)
                          downloadBlob(
                            new Blob(
                              [JSON.stringify(response.result, null, 2)],
                              { type: 'application/json' },
                            ),
                            `${drawing.code}-answer.json`,
                          );
                        setExportOpen(false);
                      }}
                    >
                      <FileText size={15} />
                      {localActive ? 'Candidate regions' : 'Answer & evidence'} <span>.json</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="viewer-shell">
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
                  className={`icon-button ${showLabels ? 'tool-active' : ''}`}
                  aria-label="Toggle object labels"
                  title="Object labels"
                  onClick={() => setShowLabels(!showLabels)}
                >
                  <Tag size={16} />
                </button>
                <div className="layer-wrap">
                  <button
                    className={`icon-button ${layersOpen ? 'tool-active' : ''}`}
                    aria-label="Drawing layers"
                    title="Drawing layers"
                    onClick={() => setLayersOpen(!layersOpen)}
                  >
                    <Layers2 size={17} />
                  </button>
                  {layersOpen && (
                    <div className="popover layer-popover">
                      <strong>Drawing layers</strong>
                      <label>
                        <input
                          type="checkbox"
                          checked
                          disabled
                          title="The original source remains visible"
                        />
                        Original source
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={showMarks}
                          onChange={(e) => setShowMarks(e.target.checked)}
                        />
                        {localActive ? 'Candidate markings' : 'Answer markings'} <span>{overlayCount}</span>
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={showLabels}
                          onChange={(e) => setShowLabels(e.target.checked)}
                        />
                        Object labels
                      </label>
                    </div>
                  )}
                </div>
                <button
                  className="icon-button"
                  aria-label={showMarks ? 'Hide markings' : 'Show markings'}
                  title={showMarks ? 'Hide markings · O' : 'Show markings · O'}
                  onClick={() => setShowMarks(!showMarks)}
                >
                  {showMarks ? <Eye size={17} /> : <EyeOff size={17} />}
                </button>
                <span className="viewer-separator" />
                <button
                  className="icon-button"
                  aria-label="Toggle answer panel"
                  title="Answer panel"
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
                  style={{ fontFamily: 'Inter, Segoe UI, Arial, sans-serif' }}
                  aria-label={`${title} source drawing with ${showMarks ? overlayCount : 0} ${localActive ? 'candidate' : 'evidence'} marks`}
                >
                  <DrawingArtwork
                    drawing={drawing}
                    imported={localActive ? displayImported : null}
                  />
                  {!asking && showMarks && (
                    localActive && candidateResponse ? <CandidateLayer
                      response={candidateResponse.result}
                      selected={selected}
                      labels={showLabels}
                      onSelect={(id) => setSelected((s) => s === id ? null : id)}
                    /> : <MarkLayer
                      marks={marks}
                      selected={selected}
                      labels={showLabels}
                      onSelect={(id) =>
                        setSelected((s) => (s === id ? null : id))
                      }
                    />
                  )}
                </svg>
              </div>
              <div className="stage-corner">
                <MousePointer2 size={12} />
                {dragging
                  ? 'Panning drawing'
                  : 'Drag to pan · Scroll to zoom · Drop files to import'}
              </div>
              {showMarks && !!overlayCount && !asking && (
                <button
                  className="overlay-legend"
                  title="Fit all answer markings"
                  onClick={() => {
                    setSelected(null);
                    resetViewport();
                  }}
                >
                  <ScanLine size={14} />
                  <strong>{overlayCount}</strong>{' '}
                  {localActive ? (language === 'fi' ? 'ehdokasta tarkistettavaksi' : 'candidates to review') : response?.intent === 'area'
                    ? 'room boundary'
                    : response?.intent === 'width'
                      ? 'dimension'
                      : t.shown}
                </button>
              )}
              {selectedMark && (
                <div className="selection-callout">
                  <span className="selection-number">
                    {selectedMark.ordinal}
                  </span>
                  <div>
                    <strong>
                      {selectedMark.label}
                      <span>{selectedMark.detail}</span>
                    </strong>
                    <small>
                      <Check size={11} />
                      {drawing.code} · Source located
                    </small>
                  </div>
                  <button
                    className="icon-button"
                    aria-label="Focus selected object"
                    title="Focus object"
                    onClick={() => focusMark(selectedMark)}
                  >
                    <Maximize size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label="Clear selection"
                    onClick={() => setSelected(null)}
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
              {(asking || importing) && (
                <div className="viewer-loading">
                  <span className="spinner" />
                  {importing
                    ? importProgress
                      ? `${language === 'fi' ? 'Tuodaan' : 'Importing'} ${importProgress.current} / ${importProgress.total} · ${importProgress.name}`
                      : language === 'fi'
                        ? 'Avataan PDF-sivua…'
                        : 'Opening PDF page…'
                    : localActive ? (language === 'fi' ? 'Paikannetaan ehdokkaita…' : 'Locating candidates…') : language === 'fi'
                      ? 'Haetaan demovastausta…'
                      : 'Locating demo evidence…'}
                </div>
              )}
              <div className="zoom-controls">
                <button
                  className="icon-button"
                  aria-label="Zoom out"
                  onClick={() => setZoom((z) => clampZoom(z - 0.15))}
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
                  onClick={() => setZoom((z) => clampZoom(z + 0.15))}
                >
                  <Plus size={16} />
                </button>
                <span />
                <button
                  className="icon-button"
                  aria-label="Rotate drawing"
                  title="Rotate · R"
                  onClick={() => setRotation((r) => (r + 90) % 360)}
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
                {localActive
                  ? imported?.file.name
                  : `${drawing.code}_${drawing.title.toLowerCase().replaceAll(' ', '_')}.svg`}
              </span>
              <div className="page-navigation">
                <button
                  className="icon-button"
                  aria-label="Previous drawing or PDF page"
                  disabled={
                    importing ||
                    (localActive
                      ? !imported || imported.page === 1
                      : DRAWINGS.indexOf(drawing) === 0)
                  }
                  onClick={() => {
                    if (localActive && imported)
                      void openPage(imported, imported.page - 1);
                    else chooseDrawing(DRAWINGS[DRAWINGS.indexOf(drawing) - 1]);
                  }}
                >
                  <ChevronLeft size={14} />
                </button>
                <span>
                  {localActive && imported
                    ? `${imported.page} / ${imported.pages}`
                    : `${DRAWINGS.indexOf(drawing) + 1} / ${DRAWINGS.length}`}
                </span>
                <button
                  className="icon-button"
                  aria-label="Next drawing or PDF page"
                  disabled={
                    importing ||
                    (localActive
                      ? !imported || imported.page >= imported.pages
                      : DRAWINGS.indexOf(drawing) === DRAWINGS.length - 1)
                  }
                  onClick={() => {
                    if (localActive && imported)
                      void openPage(imported, imported.page + 1);
                    else chooseDrawing(DRAWINGS[DRAWINGS.indexOf(drawing) + 1]);
                  }}
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
          <div className="workspace-footnote">
            <span className="footnote-icon">
              <CheckCheck size={13} />
            </span>
            {t.only}
            <span className="footnote-shortcut">
              <kbd>0</kbd> Fit <span>·</span> <kbd>R</kbd> Rotate <span>·</span>{' '}
              <kbd>O</kbd> Marks
            </span>
          </div>
        </main>

        {inspectorOpen && (
          <aside
            className="answer-panel"
            id="answer-panel"
            aria-label="Drawing answer and evidence"
          >
            <div className="answer-panel-header">
              <span className="ask-icon">
                <Sparkles size={19} strokeWidth={1.7} />
              </span>
              <div>
                <h2>{t.ask}</h2>
                <p>{localActive ? (language === 'fi' ? 'Paikanna näkyvät kohteet tästä kuvasta.' : 'Locate visible objects in this image.') : t.intro}</p>
              </div>
              <button
                className="icon-button panel-close"
                aria-label="Close answer panel"
                onClick={() => setInspectorOpen(false)}
              >
                <PanelRightClose size={17} />
              </button>
            </div>

            {localActive && candidateResponse && analysisUrl ? (
              <CandidatePanel
                response={candidateResponse.result}
                question={candidateResponse.question}
                selected={selected}
                onSelect={(id) => { setSelected((value) => value === id ? null : id); setShowMarks(true); }}
                onFocus={focusCandidate}
                imageUrl={analysisUrl}
                language={language}
              />
            ) : localActive ? (
              <div className="local-preview-state">
                <span className="empty-state-icon">
                  <FileImage size={28} />
                </span>
                <h3>
                  {language === 'fi'
                    ? 'Piirustuksesi on valmis katseltavaksi.'
                    : asking ? 'Locating candidates…' : 'Your drawing is ready to analyse.'}
                </h3>
                <p>
                  {language === 'fi'
                    ? 'Kysy näkyvistä kohteista. Kysymyksen lähettäminen lähettää tämän kuvan tai PDF-sivun Nemotronille. Tulokset ovat tarkistettavia ehdokkaita.'
                    : 'Ask about visible objects. Submitting sends this image or PDF page to Nemotron and highlights the candidates it finds for you to review.'}
                </p>
                {candidateError && <p role="alert" className="candidate-api-error">{candidateError}</p>}
                {asking && <button className="secondary-button" onClick={() => {
                  requestRef.current?.abort();
                  requestRef.current = null;
                  setAsking(false);
                  clearCandidates();
                }}>Cancel analysis</button>}
                {imported && (
                  <p className="local-file-details">
                    {fileSize(imported.file.size)} ·{' '}
                    {imported.kind === 'pdf'
                      ? `${imported.pages} ${language === 'fi' ? 'sivua' : imported.pages === 1 ? 'page' : 'pages'}`
                      : `${imported.width} × ${imported.height} px`}
                  </p>
                )}
                <button
                  className="secondary-button"
                  onClick={() => setSidebarOpen(true)}
                >
                  <FolderOpen size={14} />
                  {t.drawings} ({localDrawings.length})
                </button>
                <p className="import-local-note">{t.localNote}</p>
                <button
                  className="secondary-button"
                  onClick={() => chooseDrawing(DRAWINGS[0])}
                >
                  Explore demo answers <ArrowRight size={14} />
                </button>
              </div>
            ) : (
              response && (
                <div
                  className={`answer-content ${asking ? 'answer-pending' : ''}`}
                >
                  <div className="latest-question">
                    <span className="question-avatar">
                      <MousePointer2 size={13} />
                    </span>
                    <p>{response.question}</p>
                  </div>
                  <section
                    className={`result-card ${missing ? 'missing-result' : ''}`}
                    aria-live="polite"
                  >
                    <div className="result-eyebrow">
                      <span className="result-symbol">
                        {missing ? (
                          <CircleHelp size={13} />
                        ) : (
                          <Check size={13} />
                        )}
                      </span>
                      {missing
                        ? language === 'fi'
                          ? 'TIETO PUUTTUU'
                          : 'INFORMATION UNAVAILABLE'
                        : t.answer}
                      <span>{localActive ? '' : drawing.code}</span>
                    </div>
                    {missing ? (
                      <h3>{response.summary}</h3>
                    ) : (
                      <div className="answer-main">
                        <div className="answer-value">
                          {response.value}
                          <span>{response.unit}</span>
                        </div>
                        <strong className="answer-summary">
                          {response.summary}
                        </strong>
                      </div>
                    )}
                    <p>{response.description}</p>
                    {!missing && (
                      <button
                        className="source-citation"
                        onClick={() => {
                          setSelected(null);
                          setShowMarks(true);
                          resetViewport();
                        }}
                        title="Show all source evidence"
                      >
                        <FileText size={12} />
                        <span>
                          {drawing.code} · {title}
                        </span>
                        <ArrowRight size={12} />
                      </button>
                    )}
                  </section>
                  {!missing ? (
                    <>
                      <div
                        className="evidence-tabs"
                        role="tablist"
                        aria-label="Answer details"
                        onKeyDown={(event) => {
                          if (
                            ![
                              'ArrowLeft',
                              'ArrowRight',
                              'Home',
                              'End',
                            ].includes(event.key)
                          )
                            return;
                          event.preventDefault();
                          const next =
                            event.key === 'Home'
                              ? 'evidence'
                              : event.key === 'End'
                                ? 'calculation'
                                : activeTab === 'evidence'
                                  ? 'calculation'
                                  : 'evidence';
                          setActiveTab(next);
                          event.currentTarget
                            .querySelector<HTMLButtonElement>(`#${next}-tab`)
                            ?.focus();
                        }}
                      >
                        <button
                          role="tab"
                          id="evidence-tab"
                          aria-controls="evidence-content"
                          aria-selected={activeTab === 'evidence'}
                          tabIndex={activeTab === 'evidence' ? 0 : -1}
                          className={
                            activeTab === 'evidence' ? 'active-tab' : ''
                          }
                          onClick={() => setActiveTab('evidence')}
                        >
                          <SquareDashedMousePointer size={14} />
                          {t.objects}
                          <span>{marks.length}</span>
                        </button>
                        <button
                          role="tab"
                          id="calculation-tab"
                          aria-controls="calculation-content"
                          aria-selected={activeTab === 'calculation'}
                          tabIndex={activeTab === 'calculation' ? 0 : -1}
                          className={
                            activeTab === 'calculation' ? 'active-tab' : ''
                          }
                          onClick={() => setActiveTab('calculation')}
                        >
                          <BookOpen size={14} />
                          {t.calculation}
                        </button>
                      </div>
                      {selectedMark && (
                        <SourceContext
                          drawing={drawing}
                          mark={selectedMark}
                          language={language}
                          onFocus={() => focusMark(selectedMark)}
                        />
                      )}
                      {activeTab === 'evidence' ? (
                        <div
                          className="evidence-list"
                          role="tabpanel"
                          id="evidence-content"
                          aria-labelledby="evidence-tab"
                          aria-label="Source evidence"
                        >
                          <div className="evidence-list-caption">
                            {language === 'fi'
                              ? 'Valitse kohde paikantaaksesi sen.'
                              : 'Select an item to locate it on the drawing.'}
                          </div>
                          {marks.map((mark) => (
                            <button
                              key={mark.id}
                              className={`evidence-row ${selected === mark.id ? 'selected-row' : ''}`}
                              onClick={() => focusMark(mark)}
                              aria-pressed={selected === mark.id}
                            >
                              <span className="evidence-number">
                                {mark.ordinal}
                              </span>
                              <span className="evidence-row-copy">
                                <strong>
                                  {mark.label}
                                  <span>
                                    {mark.kind === 'area'
                                      ? 'Room'
                                      : mark.kind === 'dimension'
                                        ? 'Dimension'
                                        : response.intent === 'windows'
                                          ? 'Window'
                                          : 'Door'}
                                  </span>
                                </strong>
                                <small>{mark.detail}</small>
                              </span>
                              <span className="evidence-located">
                                <Check size={12} />
                                <ChevronRight size={13} />
                              </span>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div
                          className="calculation-list"
                          role="tabpanel"
                          id="calculation-content"
                          aria-labelledby="calculation-tab"
                          aria-label="Calculation steps"
                        >
                          {response.steps.map((step, i) => (
                            <button
                              key={i}
                              className="calculation-step"
                              onClick={() => {
                                if (step.markIds.length === 1) {
                                  const mark = marks.find(
                                    (m) => m.id === step.markIds[0],
                                  );
                                  if (mark) focusMark(mark);
                                } else {
                                  setSelected(null);
                                  setShowMarks(true);
                                  resetViewport();
                                }
                              }}
                            >
                              <span className="step-number">{i + 1}</span>
                              <span>
                                <strong>{step.title}</strong>
                                <small>{step.detail}</small>
                                {step.expression && (
                                  <code>{step.expression}</code>
                                )}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="coverage-note">
                        <CheckCheck size={14} />
                        <span>
                          {t.complete}
                          <small>
                            {marks.length} / {marks.length} {t.shown}
                          </small>
                        </span>
                        <button
                          className="icon-button"
                          aria-label="Show all matches"
                          title="Show all matches"
                          onClick={() => {
                            setSelected(null);
                            setShowMarks(true);
                            resetViewport();
                          }}
                        >
                          <Maximize size={14} />
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="missing-explanation">
                      <EyeOff size={19} />
                      <p>
                        {t.noEvidence}.{' '}
                        {language === 'fi'
                          ? 'Puuttuvaa tietoa ei tulkita nollaksi.'
                          : 'Missing information is not treated as zero.'}
                      </p>
                      <button
                        className="text-button"
                        onClick={() => queryRef.current?.focus()}
                      >
                        Ask another question <ArrowRight size={13} />
                      </button>
                    </div>
                  )}
                </div>
              )
            )}
            <div className="question-section">
              <div className="question-scope">
                <FileText size={12} />
                <span>
                  {localActive
                    ? imported?.file.name
                    : `${drawing.code} · ${title}`}
                </span>
                <span className="scope-lock">
                  <Check size={11} />
                  {language === 'fi' ? 'Vain tämä näkymä' : 'This view only'}
                </span>
              </div>
              <form className="question-form" onSubmit={submit}>
                <textarea
                  ref={queryRef}
                  aria-label="Question about the drawing"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={localActive ? (language === 'fi' ? 'Paikanna ikkunat tässä kuvassa…' : 'Locate the windows in this drawing…') : t.placeholder}
                  disabled={importing || asking}
                  maxLength={4000}
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void ask(query);
                    }
                  }}
                />
                <div className="question-form-footer">
                  <span>
                    {localActive ? (
                      language === 'fi' ? 'Näkyvä kuva → Nemotron' : 'Displayed image → Nemotron'
                    ) : (
                      <>
                        <kbd>↵</kbd>{' '}
                        {language === 'fi'
                          ? 'Kysy painamalla Enter'
                          : 'Enter to ask'}
                      </>
                    )}
                  </span>
                  <button
                    type="submit"
                    className="ask-submit"
                    aria-label={t.askButton}
                    disabled={!query.trim() || asking || importing}
                  >
                    {asking ? (
                      <span className="spinner" />
                    ) : (
                      <ArrowUp size={17} />
                    )}
                  </button>
                </div>
              </form>
              {!localActive && (
                <>
                  <div className="suggestion-label">{t.try}</div>
                  <div className="suggestion-chips">
                    {chips.map((q, i) => (
                      <button
                        key={q}
                        onClick={() => void ask(q)}
                        disabled={asking}
                      >
                        {chipNames[i]}
                        <ArrowUp size={11} className="suggestion-arrow" />
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="answer-panel-footer">
              <button
                onClick={() => setHistoryOpen(!historyOpen)}
                className="history-button"
              >
                <Clock3 size={14} />
                {localActive ? (language === 'fi' ? 'Tarkistettavat Nemotron-ehdokkaat' : 'Nemotron candidates for review') : language === 'fi'
                  ? 'Viimeisimmät kysymykset'
                  : 'Recent questions'}
                <span>{history.length}</span>
                <ChevronDown size={12} />
              </button>
              {historyOpen && (
                <div className="history-list">
                  {history.length ? (
                    history.map((q) => (
                      <button
                        key={q}
                        onClick={() => {
                          setQuery(q);
                          queryRef.current?.focus();
                        }}
                      >
                        {q}
                      </button>
                    ))
                  ) : (
                    <p>Your questions will appear here.</p>
                  )}
                </div>
              )}
              <p>
                <span className="tiny-demo-dot" />
                {language === 'fi'
                  ? 'Havainnollistavat piirustukset ja vastaukset'
                  : 'Illustrative drawings and prepared answers'}
              </p>
            </div>
          </aside>
        )}
      </div>
      {!sidebarOpen && localFileInput}
      {fileDragging && !sidebarOpen && (
        <div className="file-drop-overlay" role="status">
          <Upload size={38} />
          <strong>{t.dropTitle}</strong>
          <span>{IMPORT_FORMATS}</span>
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
