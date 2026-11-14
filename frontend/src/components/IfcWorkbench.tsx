import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Box,
  ChevronDown,
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

const labels: Record<IfcStatus, string> = {
  idle: 'Ready to open',
  reading: 'Reading model…',
  converting: 'Converting IFC…',
  rendering: 'Preparing 3D view…',
  ready: 'Model ready',
  cancelled: 'Opening cancelled',
  error: 'Model could not be opened',
};

function NativeData({ data, depth = 0 }: { data: ItemData; depth?: number }) {
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
          <details
            className="ifc-property-group"
            key={name}
            open={depth === 0 && name === 'IsDefinedBy'}
          >
            <summary>
              {name} <span>{items.length}</span>
            </summary>
            {items.map((item, index) => (
              <details
                key={index}
                className="ifc-property-group"
                open={depth < 1}
              >
                <summary>
                  {String(
                    attribute(item, 'Name') ??
                      attribute(item, '_category') ??
                      `#${attribute(item, '_localId')}`,
                  )}
                  {/(TYPE|STYLE)$/.test(
                    String(attribute(item, '_category')),
                  ) && <small>Type definition</small>}
                </summary>
                <NativeData data={item} depth={depth + 1} />
              </details>
            ))}
          </details>
        ))}
      {depth >= 8 && !!relations.length && (
        <p className="ifc-note">
          Nested property references are truncated after 8 levels.
        </p>
      )}
    </>
  );
}

function TreeNode({
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
  const button = (
    <button
      className={`ifc-tree-item ${selected === node.id && node.id !== null ? 'selected' : ''}`}
      disabled={node.id === null}
      onClick={() => node.id !== null && select(node.id)}
      title={node.category}
    >
      <Box size={12} />
      <span>{node.label}</span>
      {node.id !== null && <small>#{node.id}</small>}
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
        {button}
      </summary>
      {open && (
        <div className="ifc-tree-children">
          {node.children.map((child, index) => (
            <TreeNode
              key={`${child.id}-${index}`}
              node={child}
              selected={selected}
              select={select}
            />
          ))}
        </div>
      )}
    </details>
  ) : (
    <div className="ifc-tree-leaf">{button}</div>
  );
}

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
  const [orthographic, setOrthographic] = useState(false);
  const [storey, setStorey] = useState('');
  const [section, setSection] = useState(false);
  const [height, setHeight] = useState(0);
  const [notice, setNotice] = useState('');
  const [lookup, setLookup] = useState('');
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
    setOrthographic(false);
    setStorey('');
    setSection(false);
    setNotice('');
    report({ status: 'reading' });
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
        );
        adapterRef.current = adapter;
        const converted = await loadIfc(source, controller.signal, report);
        controller.signal.throwIfAborted();
        setHash(converted.hash);
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
        if (!controller.signal.aborted) {
          report({
            status: 'error',
            message:
              error instanceof Error
                ? error.message
                : 'The model could not be opened.',
          });
          void adapter?.dispose();
          adapterRef.current = null;
        }
      }
    })();
    return () => {
      const alreadyCancelled = controller.signal.aborted;
      controller.abort();
      adapterRef.current = null;
      void adapter?.dispose();
      if (
        !alreadyCancelled &&
        lastStatus !== 'error' &&
        lastStatus !== 'cancelled'
      )
        onStatus(source.id, 'idle');
    };
    // A status update on the library entry must not restart its renderer.
  }, [source.id, attempt]);

  const run = (operation: (adapter: IfcAdapter) => Promise<unknown> | void) => {
    const adapter = adapterRef.current;
    if (!adapter || !ready) return;
    setNotice('');
    void Promise.resolve()
      .then(() => operation(adapter))
      .catch((error) => {
        if (
          adapterRef.current === adapter &&
          !(error instanceof DOMException && error.name === 'AbortError')
        )
          setNotice(
            error instanceof Error
              ? error.message
              : 'The viewer operation failed.',
          );
      });
  };
  const select = (id: number) => run((adapter) => adapter.select(id));
  const showAll = () => {
    setStorey('');
    run((adapter) => adapter.showAll());
  };
  const cancel = () => {
    controllerRef.current?.abort();
    void adapterRef.current?.dispose();
    adapterRef.current = null;
    setState({ status: 'cancelled' });
    onStatus(source.id, 'cancelled');
  };
  const retry = () => setAttempt((value) => value + 1);

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
              setStorey(id);
              run((adapter) =>
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
            disabled={!ready}
            aria-pressed={orthographic}
            onClick={() => {
              const next = !orthographic;
              setOrthographic(next);
              run((adapter) => adapter.projection(next));
            }}
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
        <span>{ready ? 'Local 3D inspection' : labels[state.status]}</span>
      </div>
      {inspectorContainer &&
        createPortal(
          <>
            <div className="answer-panel-header">
              <span className="ask-icon">
                <Box size={20} />
              </span>
              <div>
                <h2>Model inspector</h2>
                <p>Select an object to inspect its source data.</p>
              </div>
              <button
                className="icon-button panel-close"
                aria-label="Close model inspector"
                onClick={toggleInspector}
              >
                <PanelRightClose size={17} />
              </button>
            </div>
            <div className="ifc-inspector-content">
              <p className="ifc-note">
                {source.file
                  ? 'Your IFC stays in this tab.'
                  : 'Real model · FZK-Haus by KIT.'}{' '}
                Viewing and inspection only; question answering is not
                connected.
              </p>
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
                    disabled={!ready}
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
                          setStorey('');
                          run((adapter) => adapter.isolate(selection.id));
                        }}
                      >
                        Isolate
                      </button>
                      <button
                        className="secondary-button"
                        disabled={!selection.hasGeometry}
                        onClick={() =>
                          run((adapter) => adapter.hide(selection.id))
                        }
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
          </>,
          inspectorContainer,
        )}
    </>
  );
}
