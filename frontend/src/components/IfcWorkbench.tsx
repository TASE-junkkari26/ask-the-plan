import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Box,
  ChevronDown,
  CircleAlert,
  Expand,
  Eye,
  EyeOff,
  Focus,
  Layers2,
  Minus,
  PanelRightClose,
  Plus,
  RotateCcw,
  Scissors,
  X,
} from 'lucide-react';
import type { ItemData } from '@thatopen/fragments';
import type { IfcSource, IfcStatus } from '../types';
import { attribute, createIfcAdapter } from '../ifc/adapter';
import type {
  IfcAdapter,
  ModelInfo,
  ModelNode,
  ModelSelection,
} from '../ifc/adapter';
import { loadIfc } from '../ifc/load';
import type { LoadState } from '../ifc/load';
import type { GeometryRecoveryReport } from '../ifc/geometryRecovery';
import IfcQuestionPanel from './IfcQuestionPanel';
import type { EvidenceElement } from '../ifc/evidence';

const labels: Record<IfcStatus, string> = {
  idle: 'Ready to open',
  reading: 'Reading model…',
  converting: 'Converting IFC…',
  rendering: 'Preparing 3D view…',
  ready: 'Model ready',
  cancelled: 'Opening cancelled',
  error: 'Model could not be opened',
};

const NativeData = memo(function NativeData({
  data,
  depth = 0,
}: {
  data: ItemData;
  depth?: number;
}) {
  const scalars = Object.entries(data).filter(
    ([key, value]) => !key.startsWith('_') && !Array.isArray(value),
  );
  const relations = Object.entries(data).filter(
    (entry): entry is [string, ItemData[]] =>
      Array.isArray(entry[1]) && entry[1].length > 0,
  );
  return (
    <>
      {!!scalars.length && (
        <dl className="ifc-properties">
          {scalars.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd title={!Array.isArray(value) ? value.type : undefined}>
                {!Array.isArray(value) &&
                  (value.value === null || value.value === undefined
                    ? '∅ (not set)'
                    : typeof value.value === 'object'
                      ? JSON.stringify(value.value)
                      : String(value.value))}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {depth < 8 &&
        relations.map(([name, items]) => (
          <NativeRelation key={name} name={name} items={items} depth={depth} />
        ))}
      {depth >= 8 && !!relations.length && (
        <p className="ifc-note">
          Nested property references are truncated after 8 levels.
        </p>
      )}
    </>
  );
});

function NativeRelation({
  name,
  items,
  depth,
}: {
  name: string;
  items: ItemData[];
  depth: number;
}) {
  const [open, setOpen] = useState(depth === 0 && name === 'IsDefinedBy');
  return (
    <details
      className="ifc-property-group"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {name} <span>{items.length}</span>
      </summary>
      {open &&
        items.map((item, index) => (
          <NativePropertyItem
            key={`${attribute(item, '_localId') ?? index}`}
            item={item}
            depth={depth}
          />
        ))}
    </details>
  );
}

function NativePropertyItem({
  item,
  depth,
}: {
  item: ItemData;
  depth: number;
}) {
  const [open, setOpen] = useState(depth < 1);
  return (
    <details
      className="ifc-property-group"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {String(
          attribute(item, 'Name') ??
            attribute(item, '_category') ??
            `#${attribute(item, '_localId')}`,
        )}
        {/(TYPE|STYLE)$/.test(String(attribute(item, '_category'))) && (
          <small>Type definition</small>
        )}
      </summary>
      {open && <NativeData data={item} depth={depth + 1} />}
    </details>
  );
}

const TREE_PAGE_SIZE = 100;
const TreeNode = memo(function TreeNode({
  node,
  selected,
  select,
  root = false,
}: {
  node: ModelNode;
  selected: number | null;
  select: (id: number) => void;
  root?: boolean;
}) {
  const [open, setOpen] = useState(root);
  const [visible, setVisible] = useState(TREE_PAGE_SIZE);
  const content = (
    <>
      <Box size={12} />
      <span>{node.label}</span>
      {node.id !== null && <small>#{node.id}</small>}
    </>
  );
  const item =
    node.id === null ? (
      <span className="ifc-tree-item" title={node.category}>
        {content}
      </span>
    ) : (
      <button
        className={`ifc-tree-item ${selected === node.id ? 'selected' : ''}`}
        onClick={() => select(node.id!)}
        title={node.category}
      >
        {content}
      </button>
    );
  return node.children.length ? (
    <details
      className="ifc-tree-node"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <ChevronDown size={12} />
        {item}
      </summary>
      {open && (
        <div className="ifc-tree-children">
          {node.children.slice(0, visible).map((child, index) => (
            <TreeNode
              key={`${child.id}-${index}`}
              node={child}
              selected={selected}
              select={select}
            />
          ))}
          {visible < node.children.length && (
            <button
              className="text-button"
              onClick={() => setVisible((count) => count + TREE_PAGE_SIZE)}
            >
              Show next{' '}
              {Math.min(TREE_PAGE_SIZE, node.children.length - visible)} items (
              {visible} / {node.children.length})
            </button>
          )}
        </div>
      )}
    </details>
  ) : (
    <div className="ifc-tree-leaf">{item}</div>
  );
});

export default function IfcWorkbench({
  source,
  inspectorContainer,
  inspectorOpen,
  toggleInspector,
  onStatus,
  onRemove,
}: {
  source: IfcSource;
  inspectorContainer: HTMLDivElement | null;
  inspectorOpen: boolean;
  toggleInspector: () => void;
  onStatus: (id: string, status: IfcStatus, error?: string) => void;
  onRemove?: () => void;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const adapterRef = useRef<IfcAdapter | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<LoadState>({ status: 'reading' });
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [selection, setSelection] = useState<ModelSelection | null>(null);
  const [hash, setHash] = useState('');
  const [geometryRecovery, setGeometryRecovery] =
    useState<GeometryRecoveryReport | null>(null);
  const recoveryDetailsRef = useRef<HTMLElement>(null);
  const [recoveryDetailsRequested, setRecoveryDetailsRequested] =
    useState(false);
  const [orthographic, setOrthographic] = useState(false);
  const [projectionPending, setProjectionPending] = useState(false);
  const projectionRequest = useRef(0);
  const projectionInFlight = useRef(false);
  const visibilityRequest = useRef(0);
  const confirmedStorey = useRef('');
  const [storey, setStorey] = useState('');
  const [section, setSection] = useState(false);
  const [height, setHeight] = useState(0);
  const [notice, setNotice] = useState('');
  const [lookup, setLookup] = useState('');
  const [tab, setTab] = useState<'questions' | 'inspect'>('questions');
  const busy = ['reading', 'converting', 'rendering'].includes(state.status);
  const ready = state.status === 'ready';

  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    let adapter: IfcAdapter | undefined;
    let lastStatus: IfcStatus = 'reading';
    const report = (next: LoadState) => {
      if (controller.signal.aborted) return;
      lastStatus = next.status;
      setState(next);
      onStatus(
        source.id,
        next.status,
        next.status === 'error' ? next.message : undefined,
      );
    };
    setInfo(null);
    setSelection(null);
    setHash('');
    setGeometryRecovery(null);
    setRecoveryDetailsRequested(false);
    setOrthographic(false);
    setProjectionPending(false);
    projectionInFlight.current = false;
    confirmedStorey.current = '';
    setStorey('');
    setSection(false);
    setNotice('');
    setLookup('');
    setTab('questions');
    report({ status: 'reading' });
    const dispose = (instance: IfcAdapter | undefined) => {
      // Never allow a late SDK cleanup failure to become an unhandled rejection.
      if (instance) void instance.dispose().catch(() => {});
    };
    const fail = (error: unknown) => {
      if (controller.signal.aborted) return;
      report({
        status: 'error',
        message:
          error instanceof Error
            ? error.message
            : 'The model could not be opened.',
      });
      setInfo(null);
      setSelection(null);
      setGeometryRecovery(null);
      controller.abort();
      if (adapterRef.current === adapter) adapterRef.current = null;
      dispose(adapter);
    };
    void (async () => {
      try {
        adapter = createIfcAdapter(
          hostRef.current!,
          (next) => {
            if (!controller.signal.aborted) setSelection(next);
          },
          (error) => {
            if (!controller.signal.aborted)
              setNotice(
                error instanceof Error
                  ? error.message
                  : 'The viewer operation failed.',
              );
          },
          fail,
        );
        adapterRef.current = adapter;
        const converted = await loadIfc(source, controller.signal, report);
        controller.signal.throwIfAborted();
        setHash(converted.hash);
        setGeometryRecovery(
          'geometryRecovery' in converted
            ? (converted.geometryRecovery ?? null)
            : null,
        );
        report({ status: 'rendering' });
        const loaded = await adapter.load(
          converted.bytes,
          `${source.id}-${attempt}`,
          controller.signal,
        );
        controller.signal.throwIfAborted();
        setInfo(loaded);
        setHeight((loaded.minY + loaded.maxY) / 2);
        report({ status: 'ready' });
      } catch (error) {
        fail(error);
      }
    })();
    return () => {
      const alreadyCancelled = controller.signal.aborted;
      controller.abort();
      adapterRef.current = null;
      projectionRequest.current++;
      visibilityRequest.current++;
      dispose(adapter);
      if (
        !alreadyCancelled &&
        lastStatus !== 'error' &&
        lastStatus !== 'cancelled'
      )
        onStatus(source.id, 'idle');
    };
    // A status update on the library entry must not restart its renderer.
  }, [source.id, attempt]);

  useEffect(() => {
    if (!recoveryDetailsRequested || !ready || !geometryRecovery) return;
    const details = recoveryDetailsRef.current;
    if (!details || !inspectorContainer) return;
    details.scrollIntoView({ block: 'nearest' });
    details.focus({ preventScroll: true });
    setRecoveryDetailsRequested(false);
  }, [recoveryDetailsRequested, ready, geometryRecovery, inspectorContainer]);

  const run = useCallback(
    async (operation: (adapter: IfcAdapter) => Promise<unknown> | void) => {
      const adapter = adapterRef.current;
      if (!adapter || !ready) return false;
      setNotice('');
      try {
        await operation(adapter);
        return adapterRef.current === adapter;
      } catch (error) {
        if (
          adapterRef.current === adapter &&
          !(error instanceof DOMException && error.name === 'AbortError')
        )
          setNotice(
            error instanceof Error
              ? error.message
              : 'The viewer operation failed.',
          );
        return false;
      }
    },
    [ready],
  );
  const select = useCallback(
    (id: number) => {
      void run((adapter) => adapter.select(id));
    },
    [run],
  );
  const changeVisibility = useCallback(
    (nextStorey: string, operation: (adapter: IfcAdapter) => Promise<void>) => {
      const request = ++visibilityRequest.current;
      setStorey(nextStorey);
      void run(operation).then((success) => {
        if (success) confirmedStorey.current = nextStorey;
        else if (request === visibilityRequest.current)
          setStorey(confirmedStorey.current);
      });
    },
    [run],
  );
  const showAll = () => changeVisibility('', (adapter) => adapter.showAll());
  const changeProjection = () => {
    if (projectionInFlight.current) return;
    projectionInFlight.current = true;
    const request = ++projectionRequest.current;
    const next = !orthographic;
    setProjectionPending(true);
    void run((adapter) => adapter.projection(next)).then((success) => {
      if (request !== projectionRequest.current) return;
      if (success) setOrthographic(next);
      projectionInFlight.current = false;
      setProjectionPending(false);
    });
  };
  const cancel = () => {
    controllerRef.current?.abort();
    void adapterRef.current?.dispose().catch(() => {});
    adapterRef.current = null;
    setState({ status: 'cancelled' });
    setGeometryRecovery(null);
    onStatus(source.id, 'cancelled');
  };
  const retry = () => setAttempt((value) => value + 1);
  const highlight = useCallback(async (elements: EvidenceElement[]) => {
    const adapter = adapterRef.current;
    if (!adapter) throw new DOMException('Viewer closed.', 'AbortError');
    return adapter.highlightEvidence(elements);
  }, []);
  const clearHighlights = useCallback(() => {
    void adapterRef.current?.clearEvidence().catch(() => {});
  }, []);
  const inspectEvidence = useCallback((id: number) => {
    setTab('inspect');
    select(id);
  }, [select]);

  return (
    <>
      <div className="viewer-toolbar ifc-toolbar">
        <span className="view-mode">
          <Box size={15} />
          3D model
        </span>
        <label className="ifc-storey">
          <Layers2 size={14} />
          <select
            aria-label="Model storey"
            disabled={!ready}
            value={storey}
            onChange={(event) => {
              const id = event.target.value;
              changeVisibility(id, (adapter) =>
                adapter.setStorey(
                  info?.storeys.find((node) => String(node.id) === id) ?? null,
                ),
              );
            }}
          >
            <option value="">All storeys</option>
            {info?.storeys.map((node) => (
              <option key={node.id} value={String(node.id)}>
                {node.label}
              </option>
            ))}
          </select>
        </label>
        <div className="viewer-tools">
          <button
            className={`secondary-button ifc-projection ${orthographic ? 'tool-active' : ''}`}
            disabled={!ready || projectionPending}
            aria-pressed={orthographic}
            onClick={changeProjection}
          >
            {orthographic ? 'Orthographic' : 'Perspective'}
          </button>
          <button
            className="icon-button"
            title="Fit model"
            aria-label="Fit model"
            disabled={!ready}
            onClick={() => run((adapter) => adapter.fit())}
          >
            <Expand size={17} />
          </button>
          <button
            className="icon-button"
            title="Model inspector"
            aria-label="Toggle model inspector"
            aria-expanded={inspectorOpen}
            onClick={toggleInspector}
          >
            <PanelRightClose size={17} />
          </button>
        </div>
      </div>
      <div className="ifc-stage">
        <div
          className="ifc-canvas"
          ref={hostRef}
          key={attempt}
          aria-label={`${source.name} interactive 3D model`}
        />
        {!ready && (
          <div
            className="ifc-load-overlay"
            role={state.status === 'error' ? 'alert' : 'status'}
          >
            {busy ? <span className="spinner" /> : <Box size={30} />}
            <strong>{labels[state.status]}</strong>
            {state.message && <p>{state.message}</p>}
            {state.status === 'converting' && (
              <>
                <progress
                  aria-label="IFC conversion progress"
                  value={state.progress ?? 0}
                  max={1}
                />
                <small>
                  {Math.round((state.progress ?? 0) * 100)}% · Keep this tab
                  open
                </small>
              </>
            )}
            <div className="ifc-actions">
              {busy ? (
                <button className="secondary-button" onClick={cancel}>
                  Cancel
                </button>
              ) : (
                <button className="primary-button" onClick={retry}>
                  <RotateCcw size={14} />
                  Retry
                </button>
              )}
              {onRemove && (
                <button className="secondary-button" onClick={onRemove}>
                  Remove
                </button>
              )}
            </div>
          </div>
        )}
        {ready && (
          <>
            {geometryRecovery && geometryRecovery.omittedFaceCount > 0 && (
              <div
                className="ifc-partial-banner"
                role="status"
                aria-label="Partial model geometry"
              >
                <CircleAlert size={18} aria-hidden="true" />
                <div>
                  <strong>Partial geometry · incomplete source</strong>
                  <p>
                    {geometryRecovery.omittedFaceCount.toLocaleString('en')}{' '}
                    invalid faces omitted. Source properties are retained.
                  </p>
                </div>
                <button
                  className="secondary-button"
                  onClick={() => {
                    setTab('inspect');
                    setRecoveryDetailsRequested(true);
                    if (!inspectorOpen) toggleInspector();
                  }}
                >
                  View omissions
                </button>
              </div>
            )}
            <div className="ifc-navigation-hint">
              Drag to orbit · Right-drag to pan · Scroll to zoom
            </div>
            <div className="zoom-controls">
              <button
                className="icon-button"
                aria-label="Zoom model out"
                onClick={() => run((adapter) => adapter.zoom(-2))}
              >
                <Minus size={16} />
              </button>
              <button
                className="icon-button"
                aria-label="Zoom model in"
                onClick={() => run((adapter) => adapter.zoom(2))}
              >
                <Plus size={16} />
              </button>
              <span />
              <button
                className="icon-button"
                aria-label="Fit model"
                onClick={() => run((adapter) => adapter.fit())}
              >
                <Expand size={16} />
              </button>
            </div>
          </>
        )}
      </div>
      <div className="viewer-footer">
        <span>
          <Box size={12} />
          {source.name}
        </span>
        <span>
          {ready
            ? geometryRecovery && geometryRecovery.omittedFaceCount > 0
              ? 'Partial geometry · source properties retained'
              : 'IFC source · ask & verify'
            : labels[state.status]}
        </span>
      </div>
      {inspectorContainer &&
        createPortal(
          <>
            <div className="answer-panel-header">
              <span className="ask-icon">
                <Box size={20} />
              </span>
              <div>
                <h2>Ask & verify</h2>
                <p>Source answers, linked to model elements.</p>
              </div>
              <button
                className="icon-button panel-close"
                aria-label="Close model inspector"
                onClick={toggleInspector}
              >
                <PanelRightClose size={17} />
              </button>
            </div>
            <div className="ifc-panel-tabs" role="tablist" aria-label="IFC model panel">
              <button role="tab" id="ifc-questions-tab" aria-selected={tab === 'questions'} aria-controls="ifc-questions-content" onClick={() => setTab('questions')}>Questions & evidence</button>
              <button role="tab" id="ifc-inspect-tab" aria-selected={tab === 'inspect'} aria-controls="ifc-inspect-content" onClick={() => setTab('inspect')}>Inspect source</button>
            </div>
            <div className="ifc-inspector-content">
              <div id="ifc-questions-content" role="tabpanel" aria-labelledby="ifc-questions-tab" style={{ display: tab === 'questions' ? undefined : 'none' }}>
                <IfcQuestionPanel
                  key={`${source.id}:${attempt}`}
                  source={source}
                  sourceHash={hash}
                  ready={ready}
                  section={section}
                  highlight={highlight}
                  clearHighlights={clearHighlights}
                  focus={(ids) => { void run((adapter) => adapter.fit(ids)); }}
                  isolate={(ids) => changeVisibility('', (adapter) => adapter.isolateMany(ids))}
                  onSelect={inspectEvidence}
                />
              </div>
              <div id="ifc-inspect-content" role="tabpanel" aria-labelledby="ifc-inspect-tab" style={{ display: tab === 'inspect' ? undefined : 'none' }}>
              <p className="ifc-note">
                {source.file
                  ? 'Viewing and property inspection run locally. Asking a question uploads the source to the local backend.'
                  : 'Real model · FZK-Haus by KIT.'}{' '}
              </p>
              {ready &&
                geometryRecovery &&
                geometryRecovery.omittedFaceCount > 0 && (
                  <section
                    className="ifc-recovery-details"
                    ref={recoveryDetailsRef}
                    role="note"
                    aria-label="Partial geometry details"
                    tabIndex={-1}
                  >
                    <h3>
                      <CircleAlert size={14} aria-hidden="true" />
                      Source geometry omissions
                    </h3>
                    <p>
                      The source geometry is incomplete. Invalid source faces
                      were omitted from this preview; the remaining geometry can
                      be inspected.
                    </p>
                    <dl className="ifc-properties">
                      <div>
                        <dt>Faces omitted</dt>
                        <dd>
                          {geometryRecovery.omittedFaceCount.toLocaleString(
                            'en',
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Invalid loops</dt>
                        <dd>
                          {geometryRecovery.invalidLoopCount.toLocaleString(
                            'en',
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Unresolvable point IDs</dt>
                        <dd>
                          {geometryRecovery.missingPointCount.toLocaleString(
                            'en',
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Face sets affected</dt>
                        <dd>
                          {geometryRecovery.modifiedFaceSetCount.toLocaleString(
                            'en',
                          )}
                        </dd>
                      </div>
                    </dl>
                    {!!geometryRecovery.sampleFaceIds.length && (
                      <p className="ifc-recovery-samples">
                        <strong>Omitted face STEP IDs (sample)</strong>
                        <code>
                          {geometryRecovery.sampleFaceIds
                            .map((id) => `#${id}`)
                            .join(', ')}
                        </code>
                      </p>
                    )}
                    {!!geometryRecovery.sampleMissingPointIds.length && (
                      <p className="ifc-recovery-samples">
                        <strong>Unresolvable point STEP IDs (sample)</strong>
                        <code>
                          {geometryRecovery.sampleMissingPointIds
                            .map((id) => `#${id}`)
                            .join(', ')}
                        </code>
                      </p>
                    )}
                    <p>
                      The original IFC file and source properties are retained.
                      No replacement point coordinates were created. Visible
                      geometry is partial and does not establish model
                      completeness.
                    </p>
                  </section>
                )}
              {info && !info.hasGeometry && (
                <p className="ifc-note">
                  No drawable geometry was extracted. Available source metadata
                  can still be inspected below.
                </p>
              )}
              {notice && (
                <div className="ifc-notice" role="alert">
                  {notice}
                  <button
                    className="icon-button"
                    aria-label="Dismiss viewer notice"
                    onClick={() => setNotice('')}
                  >
                    <X size={13} />
                  </button>
                </div>
              )}
              <section className="ifc-section-controls">
                <h3>View controls</h3>
                <div className="ifc-actions">
                  <button
                    className="secondary-button"
                    disabled={!ready}
                    onClick={showAll}
                  >
                    <Eye size={14} />
                    Show all objects
                  </button>
                </div>
                <label className="ifc-section-toggle">
                  <input
                    type="checkbox"
                    checked={section}
                    disabled={!ready || !info?.hasGeometry}
                    onChange={(event) => {
                      const checked = event.target.checked;
                      setSection(checked);
                      run((adapter) =>
                        adapter.section(checked ? height : null),
                      );
                    }}
                  />
                  <Scissors size={14} />
                  Horizontal section
                </label>
                {section && info && (
                  <>
                    <label className="ifc-section-height">
                      Cut height (viewer metres)
                      <output>{height.toFixed(2)}</output>
                      <input
                        aria-label="Section height"
                        type="range"
                        min={info.minY}
                        max={Math.max(info.maxY, info.minY + 0.01)}
                        step="0.01"
                        value={height}
                        onChange={(event) => {
                          const next = Number(event.target.value);
                          setHeight(next);
                          run((adapter) => adapter.section(next));
                        }}
                      />
                    </label>
                    <button
                      className="text-button"
                      onClick={() => {
                        setSection(false);
                        setHeight((info.minY + info.maxY) / 2);
                        run((adapter) => adapter.section(null));
                      }}
                    >
                      Reset section
                    </button>
                  </>
                )}
              </section>
              <section className="ifc-selection">
                <h3>Selected object</h3>
                {selection ? (
                  <>
                    <strong className="ifc-object-name">
                      {String(
                        attribute(selection.data, 'Name') ??
                          attribute(selection.data, '_category') ??
                          'Unnamed object',
                      )}
                    </strong>
                    <dl className="ifc-properties">
                      <div>
                        <dt>IFC class</dt>
                        <dd>
                          {String(
                            attribute(selection.data, '_category') ??
                              'Not extracted',
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Original STEP ID</dt>
                        <dd>#{selection.id}</dd>
                      </div>
                      <div>
                        <dt>IFC GUID</dt>
                        <dd>{selection.guid ?? 'Not present'}</dd>
                      </div>
                    </dl>
                    {!selection.hasGeometry && (
                      <p className="ifc-note">
                        This item has no drawable geometry in this preview. Its
                        extracted properties remain inspectable.
                      </p>
                    )}
                    <div className="ifc-actions">
                      <button
                        className="secondary-button"
                        disabled={!selection.hasGeometry}
                        onClick={() =>
                          run((adapter) => adapter.fit(selection.id))
                        }
                      >
                        <Focus size={13} />
                        Focus
                      </button>
                      <button
                        className="secondary-button"
                        disabled={!selection.hasGeometry}
                        onClick={() => {
                          changeVisibility('', (adapter) =>
                            adapter.isolate(selection.id),
                          );
                        }}
                      >
                        Isolate
                      </button>
                      <button
                        className="secondary-button"
                        disabled={!selection.hasGeometry}
                        onClick={() => changeVisibility(storey, (adapter) => adapter.hide(selection.id))}
                      >
                        <EyeOff size={13} />
                        Hide
                      </button>
                      <button
                        className="icon-button"
                        aria-label="Clear model selection"
                        onClick={() => run((adapter) => adapter.select(null))}
                      >
                        <X size={14} />
                      </button>
                    </div>
                    <details open className="ifc-property-group">
                      <summary>
                        Occurrence attributes & source references
                      </summary>
                      <NativeData data={selection.data} />
                    </details>
                    {selection.propertiesTruncated && (
                      <p className="ifc-note">
                        Some nested properties were omitted from this preview
                        (512 items / 8 reference levels). The source file
                        remains authoritative.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="ifc-note">
                    Click the model or choose an item below. Selecting an object
                    keeps the camera in place; Focus moves to it.
                  </p>
                )}
              </section>
              {info && (
                <section className="ifc-hierarchy">
                  <h3>Model structure</h3>
                  <form
                    className="ifc-id-lookup"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const id = Number(lookup.replace(/^#/, ''));
                      if (Number.isSafeInteger(id) && id > 0) select(id);
                    }}
                  >
                    <input
                      aria-label="Find original STEP ID"
                      placeholder="Original STEP ID, e.g. #123"
                      value={lookup}
                      onChange={(event) => setLookup(event.target.value)}
                    />
                    <button
                      className="secondary-button"
                      type="submit"
                      disabled={!/^#?[1-9]\d*$/.test(lookup)}
                    >
                      Find
                    </button>
                  </form>
                  <TreeNode
                    node={info.tree}
                    selected={selection?.id ?? null}
                    select={select}
                    root
                  />
                </section>
              )}
              {!!info?.units.length && (
                <details className="ifc-property-group">
                  <summary>Project units (source values)</summary>
                  {info.units.map((item, i) => (
                    <NativeData key={i} data={item} />
                  ))}
                </details>
              )}
              {hash && (
                <details className="ifc-provenance">
                  <summary>Source identity & limitations</summary>
                  <p>SHA-256</p>
                  <code>{hash}</code>
                  <p>
                    Native IFC GUID and original STEP IDs identify source items
                    in this revision. Viewer IDs are separate from backend
                    canonical entity IDs. Geometry is centred for display;
                    source property values are preserved. This preview is not a
                    complete IFC inventory or an analysis result.
                  </p>
                  <p>
                    Only one model is rendered. The most recent converted model
                    is cached in memory; refreshing clears local imports.
                  </p>
                  {!source.file && (
                    <a
                      href="https://www.ifcwiki.org/index.php?title=KIT_IFC_Examples&oldid=552"
                      target="_blank"
                      rel="noreferrer"
                    >
                      KIT IFC Examples · source and attribution
                    </a>
                  )}
                </details>
              )}
              </div>
            </div>
          </>,
          inspectorContainer,
        )}
    </>
  );
}
