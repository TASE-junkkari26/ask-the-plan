import type { FragmentsModel, ItemData } from '@thatopen/fragments';

const forwardRelations = new Set([
  'IsDefinedBy',
  'IsTypedBy',
  'HasPropertySets',
  'HasProperties',
  'Quantities',
  'Unit',
  'UnitsInContext',
  'Units',
  'ConversionFactor',
  'UnitComponent',
  'Elements',
]);

/** Read only forward property/unit references. IFC inverse relations form cycles.
 * Do not ask the SDK for an unbounded recursive graph or hand a cyclic graph to React.
 */
export async function readSourceProperties(
  model: Pick<FragmentsModel, 'getItemsData' | 'getRelations'>,
  roots: number[],
  checkActive: () => void,
  limit = 512,
) {
  if (!Number.isSafeInteger(limit) || limit < 1)
    throw new RangeError(
      'The property preview limit must be a positive integer.',
    );
  const attributes = new Map<number, ItemData>();
  const links = new Map<number, Record<string, number[]>>();
  let frontier = [...new Set(roots.slice(0, limit))];
  let truncated = roots.length > limit;
  for (let depth = 0; depth < 8 && frontier.length; depth++) {
    checkActive();
    const unseen = [...new Set(frontier)].filter((id) => !attributes.has(id));
    const ids = unseen.slice(0, Math.max(0, limit - attributes.size));
    if (ids.length < unseen.length) truncated = true;
    if (!ids.length) break;
    const [items, relations] = await Promise.all([
      model.getItemsData(ids, {
        attributesDefault: true,
        relations: {},
        relationsDefault: { attributes: false, relations: false },
      }),
      model.getRelations(ids),
    ]);
    checkActive();
    ids.forEach((id, index) => attributes.set(id, items[index] ?? {}));
    const next = new Set<number>();
    const available = limit - attributes.size;
    for (const [id, relation] of relations) {
      const forward: Record<string, number[]> = {};
      for (const [name, references] of Object.entries(relation.data)) {
        if (!forwardRelations.has(name)) continue;
        // The SDK returns complete relation arrays. Bound our copies, frontier,
        // and work before expanding them; spreading a large array can overflow
        // the JS argument stack even though the eventual preview is capped.
        if (references.length > limit) truncated = true;
        const retained = new Set<number>();
        for (const child of references.slice(0, limit)) {
          if (attributes.has(child) || next.has(child)) retained.add(child);
          else if (next.size < available) {
            next.add(child);
            retained.add(child);
          } else truncated = true;
        }
        if (retained.size) forward[name] = [...retained];
      }
      links.set(id, forward);
    }
    frontier = [...next];
    if (depth === 7 && frontier.length) truncated = true;
  }
  let remaining = limit;
  const build = (id: number, ancestors: Set<number>, depth = 0): ItemData => {
    if (remaining <= 0 || depth >= 8) {
      truncated = true;
      return {};
    }
    remaining--;
    const data = { ...attributes.get(id) };
    const visited = new Set(ancestors).add(id);
    for (const [name, ids] of Object.entries(links.get(id) ?? {})) {
      const children: ItemData[] = [];
      for (const child of ids) {
        if (visited.has(child) || !attributes.has(child)) continue;
        if (remaining <= 0) {
          truncated = true;
          break;
        }
        const item = build(child, visited, depth + 1);
        if (Object.keys(item).length) children.push(item);
      }
      if (children.length) data[name] = children;
    }
    return data;
  };
  return {
    data: roots.slice(0, limit).map((id) => build(id, new Set())),
    truncated,
  };
}
