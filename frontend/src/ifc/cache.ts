/** One converted buffer for the entire tab, never one per library entry. No SDK imports. */
export class SingleModelCache {
  private entry?: { sourceId: string; key: string; bytes: Uint8Array };
  get(key: string) {
    return this.entry?.key === key ? this.entry.bytes : undefined;
  }
  set(sourceId: string, key: string, bytes: Uint8Array) {
    this.entry = { sourceId, key, bytes };
  }
  forget(sourceId: string) {
    if (this.entry?.sourceId === sourceId) this.entry = undefined;
  }
  clear() {
    this.entry = undefined;
  }
}
export const ifcCache = new SingleModelCache();
export const forgetIfc = (sourceId: string) => ifcCache.forget(sourceId);
