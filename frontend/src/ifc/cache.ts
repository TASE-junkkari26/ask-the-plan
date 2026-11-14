/** One converted buffer for the entire tab, never one per library entry. No SDK imports. */
export class SingleModelCache {
  private entry?: { sourceIds: Set<string>; key: string; bytes: Uint8Array };
  private fileHashes = new WeakMap<File, string>();
  private generation = 0;
  private loadingSourceId?: string;
  beginLoad(sourceId: string) {
    this.loadingSourceId = sourceId;
    return ++this.generation;
  }
  isCurrent(generation: number) {
    return generation === this.generation;
  }
  getFileHash(file: File) {
    return this.fileHashes.get(file);
  }
  rememberFileHash(file: File, hash: string) {
    this.fileHashes.set(file, hash);
  }
  get(key: string, sourceId?: string) {
    if (this.entry?.key !== key) return undefined;
    if (sourceId) this.entry.sourceIds.add(sourceId);
    return this.entry.bytes;
  }
  set(sourceId: string, key: string, bytes: Uint8Array) {
    if (this.entry?.key === key && this.entry.bytes === bytes) {
      this.entry.sourceIds.add(sourceId);
      return;
    }
    this.entry = { sourceIds: new Set([sourceId]), key, bytes };
  }
  forget(sourceId: string) {
    if (this.entry?.sourceIds.delete(sourceId) && !this.entry.sourceIds.size)
      this.entry = undefined;
    if (this.loadingSourceId === sourceId) {
      this.loadingSourceId = undefined;
      this.generation++;
    }
  }
  evictBuffer() {
    this.entry = undefined;
  }
  clear() {
    this.entry = undefined;
    this.fileHashes = new WeakMap();
    this.loadingSourceId = undefined;
    this.generation++;
  }
}
export const ifcCache = new SingleModelCache();
export const forgetIfc = (sourceId: string) => ifcCache.forget(sourceId);
