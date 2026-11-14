import * as OBC from '@thatopen/components';
import * as OBF from '@thatopen/components-front';
import type {
  FragmentsModel,
  ItemData,
  SpatialTreeItem,
} from '@thatopen/fragments';
import { RenderedFaces } from '@thatopen/fragments';
import fragmentWorkerUrl from '@thatopen/fragments/worker?url';
import * as THREE from 'three';
import { readSourceProperties } from './properties';

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
) {
  const components = new OBC.Components();
  let disposed = false;
  let selectionVersion = 0;
  let model: FragmentsModel | undefined;
  let geometryIds = new Set<number>();
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
    });
    world.renderer.showLogo = false;
    world.renderer.three.setPixelRatio(Math.min(devicePixelRatio, 2));
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
    highlighter.setup({
      world,
      autoHighlightOnClick: true,
      selectMaterialDefinition: {
        color: new THREE.Color('#74aa48'),
        opacity: 0.85,
        transparent: true,
        renderedFaces: RenderedFaces.TWO,
      },
    });
    highlighter.multiple = 'none';
    highlighter.zoomToSelection = false;
    const hider = components.get(OBC.Hider);
    const plane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
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
      if (!disposed) safe(fragments.core.update());
    };
    world.camera.controls.addEventListener('update', update);
    const cameraChanged = () => {
      if (!disposed && model) {
        model.useCamera(world.camera.three);
        safe(fragments.core.update(true));
      }
    };
    world.camera.projection.onChanged.add(cameraChanged);
    const resize = new ResizeObserver(() => {
      if (!disposed) {
        world.renderer!.resize();
        world.camera.updateAspect();
        update();
      }
    });
    resize.observe(host);
    const contextLost = (event: Event) => {
      event.preventDefault();
      if (!disposed)
        onError(
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
      const id = Object.values(map)[0]?.values().next().value;
      safe(inspect(typeof id === 'number' ? id : null));
    });
    highlighter.events.select.onClear.add(() => {
      if (!disposed) safe(inspect(null));
    });

    const map = (ids: number[]): OBC.ModelIdMap =>
      model ? { [model.modelId]: new Set(ids) } : {};
    async function fit(id?: number) {
      if (!model || disposed) return;
      const box =
        id === undefined ? model.box.clone() : await model.getMergedBox([id]);
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
          const [tree, ids, projects] = await Promise.all([
            model.getSpatialStructure(),
            model.getItemsIdsWithGeometry(),
            model.getItemsOfCategories([/^IFCPROJECT$/]),
          ]);
          signal.throwIfAborted();
          geometryIds = new Set(ids);
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
      async select(id: number | null) {
        if (disposed || !model) return;
        if (id !== null && geometryIds.has(id))
          await highlighter.highlightByID('select', map([id]), true, false);
        else {
          await highlighter.clear('select');
          if (!disposed) await inspect(id);
        }
      },
      async setStorey(node: ModelNode | null) {
        if (disposed || !model) return;
        if (!node) {
          await hider.set(true);
          return;
        }
        const ids: number[] = [];
        const collect = (n: ModelNode) => {
          if (n.id !== null) ids.push(n.id);
          n.children.forEach(collect);
        };
        collect(node);
        await hider.isolate(map(ids));
      },
      async hide(id: number) {
        if (!disposed) await hider.set(false, map([id]));
      },
      async isolate(id: number) {
        if (!disposed) await hider.isolate(map([id]));
      },
      async showAll() {
        if (!disposed) await hider.set(true);
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
        await fragments.core.update(true);
      },
      async dispose() {
        if (disposed) return;
        disposed = true;
        selectionVersion++;
        resize.disconnect();
        world.camera.controls.removeEventListener('update', update);
        world.camera.projection.onChanged.remove(cameraChanged);
        world.renderer!.three.domElement.removeEventListener(
          'webglcontextlost',
          contextLost,
        );
        // Components disposes only this adapter's canvas. Never clear the host:
        // StrictMode may already have mounted a replacement renderer there.
        components.enabled = false;
        try {
          await highlighter.dispose();
          await fragments.core.dispose();
        } finally {
          components.dispose();
          model = undefined;
          geometryIds.clear();
        }
      },
    };
  } catch (error) {
    components.dispose();
    throw error;
  }
}
export type IfcAdapter = ReturnType<typeof createIfcAdapter>;
