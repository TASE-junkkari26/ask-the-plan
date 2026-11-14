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
  const attributes = new Map<number, ItemData>();
  const links = new Map<number, Record<string, number[]>>();
  let frontier = roots;
  let truncated = false;
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
    frontier = [];
    for (const [id, relation] of relations) {
      const forward = Object.fromEntries(
        Object.entries(relation.data).filter(([name]) =>
          forwardRelations.has(name),
        ),
      );
      links.set(id, forward);
      frontier.push(...Object.values(forward).flat());
    }
    if (depth === 7 && frontier.some((id) => !attributes.has(id)))
      truncated = true;
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
      const children = ids.filter(
        (child) => !visited.has(child) && attributes.has(child),
      );
      if (children.length)
        data[name] = children
          .map((child) => build(child, visited, depth + 1))
          .filter((child) => Object.keys(child).length > 0);
    }
    return data;
  };
  return { data: roots.map((id) => build(id, new Set())), truncated };
}
