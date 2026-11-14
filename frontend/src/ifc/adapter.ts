import * as OBC from '@thatopen/components';
import * as OBF from '@thatopen/components-front';
import type {
  BIMMaterial,
  FragmentsModel,
  ItemData,
  SpatialTreeItem,
} from '@thatopen/fragments';
import { RenderedFaces } from '@thatopen/fragments';
import fragmentWorkerUrl from '@thatopen/fragments/worker?url';
import * as THREE from 'three';
import { readSourceProperties } from './properties';
import { clippingRange, renderPixelRatio, styleIfcSurface } from './rendering';
import { FrameTask, TaskQueue } from './tasks';
import { resolveEvidenceElements } from './evidence';
import type { EvidenceElement } from './evidence';

export interface ModelNode {
  id: number | null;
  category: string;
  label: string;
  children: ModelNode[];
}
export interface ModelSelection {
  id: number;
  guid: string | null;
  data: ItemData;
  hasGeometry: boolean;
  propertiesTruncated: boolean;
}
export interface ModelInfo {
  hasGeometry: boolean;
  tree: ModelNode;
  storeys: ModelNode[];
  units: ItemData[];
  minY: number;
  maxY: number;
}
export function attribute(data: ItemData | undefined, name: string): unknown {
  const value = data?.[name];
  return value && !Array.isArray(value) ? value.value : undefined;
}

/** Owns all scene, camera, worker, and GPU state. React receives only plain metadata. */
export function createIfcAdapter(
  host: HTMLDivElement,
  onSelection: (selection: ModelSelection | null) => void,
  onError: (error: unknown) => void,
  onFatalError: (error: Error) => void = onError,
) {
  const components = new OBC.Components();
  let disposed = false;
  let selectionVersion = 0;
  let model: FragmentsModel | undefined;
  let geometryIds = new Set<number>();
  let visibleIds = new Set<number>();
  let bounds: THREE.Box3 | undefined;
  let disposePromise: Promise<void> | null = null;
  const worlds = components.get(OBC.Worlds);
  const world = worlds.create<
    OBC.SimpleScene,
    OBC.OrthoPerspectiveCamera,
    OBC.SimpleRenderer
  >();
  try {
    world.scene = new OBC.SimpleScene(components);
    world.scene.setup();
    world.scene.three.background = new THREE.Color('#eef1e9');
    world.renderer = new OBC.SimpleRenderer(components, host, {
      antialias: true,
      alpha: false,
      reversedDepthBuffer: true,
    });
    world.renderer.showLogo = false;
    world.renderer.mode = OBC.RendererMode.MANUAL;
    world.renderer.needsUpdate = true;
    world.camera = new OBC.OrthoPerspectiveCamera(components);
    components.init();
  } catch (error) {
    try {
      components.dispose();
    } catch {
      // A failed renderer setup can leave the SDK world without a camera.
      // Preserve the useful graphics error instead of its cleanup error.
    }
    throw new Error(
      `3D rendering is unavailable. Enable WebGL 2 / hardware acceleration and reopen the model. ${error instanceof Error ? error.message : ''}`,
    );
  }
  try {
    const fragments = components.get(OBC.FragmentsManager);
    fragments.init(fragmentWorkerUrl, { maxWorkers: 2 });
    const highlighter = components.get(OBF.Highlighter);
    const selectionColor = new THREE.Color('#74aa48');
    const answerColor = new THREE.Color('#2680c2');
    highlighter.setup({
      world,
      autoHighlightOnClick: true,
      selectMaterialDefinition: {
        color: selectionColor,
        opacity: 0.85,
        transparent: true,
        renderedFaces: RenderedFaces.TWO,
        depthWrite: false,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -1,
      },
    });
    highlighter.multiple = 'none';
    highlighter.zoomToSelection = false;
    highlighter.styles.set('answer', {
      color: answerColor,
      opacity: 0.9,
      transparent: true,
      renderedFaces: RenderedFaces.TWO,
      depthWrite: false,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -1,
      priority: 1,
    });
    const hider = components.get(OBC.Hider);
    const plane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
    const visibility = new TaskQueue();
    const selectionTasks = new TaskQueue();
    const requestRender = () => {
      if (!disposed) world.renderer!.needsUpdate = true;
    };
    const createPulse = (baseColor: THREE.Color, peakColor: string) => ({
      baseColor,
      peakColor: new THREE.Color(peakColor),
      color: baseColor.clone(),
      materials: new Set<BIMMaterial>(),
      startedAt: 0,
    });
    const highlightPulses = new Map([
      ['select', createPulse(selectionColor, '#c2df78')],
      ['answer', createPulse(answerColor, '#82c9ed')],
    ]);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let lastPulseUpdate = 0;
    const colorHighlightMaterial = (material: BIMMaterial, pulseColor: THREE.Color) => {
      const color =
        'isLodMaterial' in material ? material.lodColor : material.color;
      color.copy(pulseColor);
    };
    const resetHighlightPulse = (name: string) => {
      const pulse = highlightPulses.get(name)!;
      pulse.startedAt = performance.now();
      lastPulseUpdate = 0;
      pulse.color.copy(pulse.baseColor);
      pulse.materials.forEach((material) => colorHighlightMaterial(material, pulse.color));
      requestRender();
    };
    const resetHighlightPulses = () => {
      for (const name of highlightPulses.keys()) resetHighlightPulse(name);
    };
    const hasVisibleHighlight = (name: string) => {
      for (const ids of Object.values(highlighter.selection[name]))
        for (const id of ids)
          if (visibleIds.has(id)) return true;
      return false;
    };
    const updateHighlightPulses = () => {
      if (disposed || document.hidden || reducedMotion.matches) return;
      const now = performance.now();
      if (now - lastPulseUpdate < 1000 / 30) return;
      lastPulseUpdate = now;
      for (const [name, pulse] of highlightPulses) {
        if (!pulse.materials.size || !hasVisibleHighlight(name)) continue;
        const blend =
          (1 - Math.cos(((now - pulse.startedAt) * 2 * Math.PI) / 4000)) / 2;
        pulse.color.lerpColors(pulse.baseColor, pulse.peakColor, blend);
        // Recolor the live materials; re-highlighting would rebuild worker state each frame.
        pulse.materials.forEach((material) => colorHighlightMaterial(material, pulse.color));
        requestRender();
      }
    };
    for (const name of highlightPulses.keys()) {
      const reset = () => { if (!disposed) resetHighlightPulse(name); };
      highlighter.events[name].onHighlight.add(reset);
      highlighter.events[name].onClear.add(reset);
    }
    const sectionUpdates = new FrameTask(async () => {
      if (!disposed) {
        await fragments.core.update(true);
        requestRender();
      }
    });
    const materialAdded = ({ value }: { value: BIMMaterial }) => {
      styleIfcSurface(value);
      const pulse = highlightPulses.get(value.userData.customId);
      if (pulse) {
        pulse.materials.add(value);
        colorHighlightMaterial(value, pulse.color);
      }
      requestRender();
    };
    const materialRemoved = ({ value }: { value: BIMMaterial }) => {
      for (const pulse of highlightPulses.values()) pulse.materials.delete(value);
    };
    fragments.core.models.materials.list.onItemSet.add(materialAdded);
    fragments.core.models.materials.list.onBeforeDelete.add(materialRemoved);
    const updateClipping = () => {
      if (!bounds || disposed) return;
      const range = clippingRange(world.camera.three.position, bounds);
      for (const camera of [world.camera.threePersp, world.camera.threeOrtho]) {
        camera.near = range.near;
        camera.far = range.far;
        camera.updateProjectionMatrix();
      }
    };
    const updateResolution = () => {
      if (disposed) return;
      const ratio = renderPixelRatio(
        host.clientWidth,
        host.clientHeight,
        devicePixelRatio,
      );
      if (world.renderer!.three.getPixelRatio() !== ratio)
        world.renderer!.three.setPixelRatio(ratio);
      requestRender();
    };
    world.renderer!.onResize.add(updateResolution);
    updateResolution();
    const safe = (promise: Promise<unknown>) => {
      void promise.catch((error) => {
        if (
          !disposed &&
          !(error instanceof DOMException && error.name === 'AbortError')
        )
          onError(error);
      });
    };
    const update = () => {
      if (!disposed) {
        updateClipping();
        requestRender();
        safe(fragments.core.update());
      }
    };
    world.camera.controls.addEventListener('update', update);
    const cameraChanged = () => {
      if (!disposed && model) {
        updateClipping();
        model.useCamera(world.camera.three);
        requestRender();
        safe(fragments.core.update(true));
      }
    };
    world.camera.projection.onChanged.add(cameraChanged);
    const contextLost = (event: Event) => {
      event.preventDefault();
      if (!disposed)
        onFatalError(
          new Error(
            'The graphics context was lost. Reopen the model to retry.',
          ),
        );
    };
    world.renderer!.three.domElement.addEventListener(
      'webglcontextlost',
      contextLost,
    );

    async function inspect(id: number | null) {
      const version = ++selectionVersion;
      if (id === null || !model) {
        onSelection(null);
        return;
      }
      const check = () => {
        if (disposed || version !== selectionVersion)
          throw new DOMException('Selection changed.', 'AbortError');
      };
      onSelection(null);
      const [properties, guids] = await Promise.all([
        readSourceProperties(model, [id], check),
        model.getGuidsByLocalIds([id]),
      ]);
      const data = properties.data;
      if (!attribute(data[0], '_category'))
        throw new Error(
          `No extracted object has STEP ID #${id} in this model.`,
        );
      if (!disposed && version === selectionVersion)
        onSelection({
          id,
          guid: guids[0] ?? null,
          data: data[0] ?? {},
          hasGeometry: geometryIds.has(id),
          propertiesTruncated: properties.truncated,
        });
    }
    highlighter.events.select.onHighlight.add((map) => {
      if (disposed) return;
      const id = Object.values(map)[0]?.values().next().value;
      safe(inspect(typeof id === 'number' ? id : null));
    });
    highlighter.events.select.onClear.add(() => {
      if (!disposed) {
        safe(inspect(null));
      }
    });

    const map = (ids: number[]): OBC.ModelIdMap =>
      model ? { [model.modelId]: new Set(ids) } : {};
    async function fit(id?: number | number[]) {
      if (!model || disposed) return;
      const box =
        id === undefined ? model.box.clone() : await model.getMergedBox(Array.isArray(id) ? id : [id]);
      if (disposed || box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const distance = Math.max(size.length(), 2);
      await world.camera.controls.setLookAt(
        center.x + distance,
        center.y + distance * 0.65,
        center.z + distance,
        center.x,
        center.y,
        center.z,
        false,
      );
      if (!disposed) {
        const sphere = box.getBoundingSphere(new THREE.Sphere());
        sphere.radius *= 1.1;
        await world.camera.controls.fitToSphere(sphere, false);
      }
      update();
    }
    world.onBeforeUpdate.add(updateHighlightPulses);
    reducedMotion.addEventListener('change', resetHighlightPulses);
    document.addEventListener('visibilitychange', resetHighlightPulses);
    return {
      async load(
        bytes: Uint8Array,
        modelId: string,
        signal: AbortSignal,
      ): Promise<ModelInfo> {
        signal.throwIfAborted();
        const workerResponse = await fetch(fragmentWorkerUrl, {
          method: 'HEAD',
          signal,
        });
        if (
          !workerResponse.ok ||
          workerResponse.headers.get('content-type')?.includes('text/html')
        )
          throw new Error(
            'The 3D model worker is missing. Rebuild the frontend and check its asset paths.',
          );
        const abort = () => fragments.core.abort(modelId);
        signal.addEventListener('abort', abort, { once: true });
        try {
          // The cache retains its own buffer; the SDK may transfer the supplied copy.
          model = await fragments.core.load(bytes.slice(), {
            modelId,
            camera: world.camera.three,
            clippingPlanes: world.renderer!.clippingPlanes,
          });
          signal.throwIfAborted();
          if (disposed) throw new DOMException('Viewer closed.', 'AbortError');
          model.useCamera(world.camera.three);
          world.scene.three.add(model.object);
          model.object.updateMatrixWorld(true);
          bounds = model.box;
          const range = clippingRange(world.camera.three.position, bounds);
          world.camera.controls.minDistance = Math.min(
            0.1,
            Math.max(0.005, range.radius * 0.0001),
          );
          model.onViewUpdated.add(requestRender);
          model.tiles.onItemSet.add(requestRender);
          model.tiles.onBeforeDelete.add(requestRender);
          updateClipping();
          requestRender();
          const [tree, ids, projects] = await Promise.all([
            model.getSpatialStructure(),
            model.getItemsIdsWithGeometry(),
            model.getItemsOfCategories([/^IFCPROJECT$/]),
          ]);
          signal.throwIfAborted();
          geometryIds = new Set(ids);
          visibleIds = new Set(ids);
          const spatialIds: number[] = [];
          // SDK trees alternate category groups (no ID) and items (no category).
          const collect = (node: SpatialTreeItem, parentCategory = '') => {
            const category = node.category ?? parentCategory;
            if (
              node.localId !== null &&
              /^(IFCPROJECT|IFCSITE|IFCBUILDING|IFCBUILDINGSTOREY)$/.test(
                category,
              )
            )
              spatialIds.push(node.localId);
            node.children?.forEach((child) => collect(child, category));
          };
          collect(tree);
          const names = spatialIds.length
            ? await model.getItemsData(spatialIds)
            : [];
          signal.throwIfAborted();
          const nameMap = new Map(
            names.map((item) => [
              Number(attribute(item, '_localId')),
              String(attribute(item, 'Name') ?? ''),
            ]),
          );
          const storeys: ModelNode[] = [];
          const normalize = (
            item: SpatialTreeItem,
            parentCategory = 'Model',
          ): ModelNode => {
            const category = item.category ?? parentCategory;
            const node: ModelNode = {
              id: item.localId,
              category,
              label: nameMap.get(item.localId ?? -1) || category,
              children:
                item.children?.map((child) => normalize(child, category)) ?? [],
            };
            if (category === 'IFCBUILDINGSTOREY' && item.localId !== null)
              storeys.push(node);
            return node;
          };
          const normalized = normalize(tree);
          const projectIds = Object.values(projects).flat();
          const units = projectIds.length
            ? (
                await readSourceProperties(model, projectIds, () =>
                  signal.throwIfAborted(),
                )
              ).data
            : [];
          signal.throwIfAborted();
          await fit();
          await fragments.core.update(true);
          requestRender();
          signal.throwIfAborted();
          return {
            hasGeometry: ids.length > 0 && !model.box.isEmpty(),
            tree: normalized,
            storeys,
            units,
            minY: Number.isFinite(model.box.min.y) ? model.box.min.y : 0,
            maxY: Number.isFinite(model.box.max.y) ? model.box.max.y : 1,
          };
        } finally {
          signal.removeEventListener('abort', abort);
        }
      },
      fit,
      /** Visibility membership, independent of camera/frustum/occlusion. */
      async getViewStepIds() {
        const ids = await visibility.run(async () => [...visibleIds].sort((a, b) => a - b));
        if (!ids || disposed) throw new DOMException('Viewer closed.', 'AbortError');
        return ids;
      },
      highlightEvidence(elements: EvidenceElement[]) {
        return selectionTasks.run(async () => {
          if (disposed || !model) throw new DOMException('Viewer closed.', 'AbortError');
          const ids = [...new Set(elements.flatMap((element) =>
            element.step_id != null && geometryIds.has(element.step_id) ? [element.step_id] : [],
          ))];
          const guids = ids.length ? await model.getGuidsByLocalIds(ids) : [];
          if (disposed) throw new DOMException('Viewer closed.', 'AbortError');
          const report = resolveEvidenceElements(elements, geometryIds,
            new Map(ids.map((id, index) => [id, guids[index] ?? null])));
          await highlighter.clear('answer');
          if (report.stepIds.length)
            await highlighter.highlightByID('answer', map(report.stepIds), true, false);
          requestRender();
          return { ...report, hiddenStepIds: report.stepIds.filter((id) => !visibleIds.has(id)) };
        });
      },
      clearEvidence() {
        return selectionTasks.run(async () => {
          if (!disposed) {
            await highlighter.clear('answer');
            requestRender();
          }
        });
      },
      isolateMany(ids: number[]) {
        return visibility.run(async () => {
          if (!disposed) {
            const drawable = ids.filter((id) => geometryIds.has(id));
            await hider.isolate(map(drawable));
            visibleIds = new Set(drawable);
            requestRender();
          }
        });
      },
      select(id: number | null) {
        return selectionTasks.run(async () => {
          if (disposed || !model) return;
          if (id !== null && geometryIds.has(id))
            await highlighter.highlightByID('select', map([id]), true, false);
          else {
            await highlighter.clear('select');
            if (!disposed) await inspect(id);
          }
          requestRender();
        });
      },
      async setStorey(node: ModelNode | null) {
        if (disposed || !model) return;
        if (!node)
          return visibility.run(async () => {
            if (!disposed) {
              await hider.set(true);
              visibleIds = new Set(geometryIds);
              requestRender();
            }
          });
        const ids: number[] = [];
        const collect = (n: ModelNode) => {
          if (n.id !== null) ids.push(n.id);
          n.children.forEach(collect);
        };
        collect(node);
        return visibility.run(async () => {
          if (!disposed) {
            await hider.isolate(map(ids));
            visibleIds = new Set(ids.filter((id) => geometryIds.has(id)));
            requestRender();
          }
        });
      },
      async hide(id: number) {
        return visibility.run(async () => {
          if (!disposed) {
            await hider.set(false, map([id]));
            visibleIds.delete(id);
            requestRender();
          }
        });
      },
      async isolate(id: number) {
        return visibility.run(async () => {
          if (!disposed) {
            await hider.isolate(map([id]));
            visibleIds = new Set(geometryIds.has(id) ? [id] : []);
            requestRender();
          }
        });
      },
      async showAll() {
        return visibility.run(async () => {
          if (!disposed) {
            await hider.set(true);
            visibleIds = new Set(geometryIds);
            requestRender();
          }
        });
      },
      async projection(orthographic: boolean) {
        if (!disposed)
          await world.camera.projection.set(
            orthographic ? 'Orthographic' : 'Perspective',
          );
      },
      zoom(delta: number) {
        if (!disposed) safe(world.camera.controls.dolly(delta, true));
      },
      async section(height: number | null) {
        if (disposed) return;
        plane.constant = height ?? 0;
        world.renderer!.setPlane(height !== null, plane);
        requestRender();
        await sectionUpdates.request();
      },
      dispose() {
        if (disposePromise) return disposePromise;
        disposed = true;
        selectionVersion++;
        sectionUpdates.dispose();
        visibility.dispose();
        selectionTasks.dispose();
        world.onBeforeUpdate.remove(updateHighlightPulses);
        reducedMotion.removeEventListener('change', resetHighlightPulses);
        document.removeEventListener('visibilitychange', resetHighlightPulses);
        for (const pulse of highlightPulses.values()) pulse.materials.clear();
        world.renderer!.onResize.remove(updateResolution);
        fragments.core.models.materials.list.onItemSet.remove(materialAdded);
        fragments.core.models.materials.list.onBeforeDelete.remove(materialRemoved);
        model?.onViewUpdated.remove(requestRender);
        model?.tiles.onItemSet.remove(requestRender);
        model?.tiles.onBeforeDelete.remove(requestRender);
        world.camera.controls.removeEventListener('update', update);
        world.camera.projection.onChanged.remove(cameraChanged);
        world.renderer!.three.domElement.removeEventListener(
          'webglcontextlost',
          contextLost,
        );
        // Components disposes only this adapter's canvas. Never clear the host:
        // StrictMode may already have mounted a replacement renderer there.
        components.enabled = false;
        disposePromise = (async () => {
          // Release every resource even if an earlier SDK cleanup step fails.
          try {
            await highlighter.dispose();
          } catch {
            /* continue cleanup */
          }
          try {
            await fragments.core.dispose();
          } catch {
            /* continue cleanup */
          }
          try {
            components.dispose();
          } catch {
            /* partially initialized/disposed world */
          }
          model = undefined;
          bounds = undefined;
          geometryIds.clear();
          visibleIds.clear();
        })();
        return disposePromise;
      },
    };
  } catch (error) {
    components.dispose();
    throw error;
  }
}
export type IfcAdapter = ReturnType<typeof createIfcAdapter>;
