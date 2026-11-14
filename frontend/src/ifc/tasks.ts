/** Collapse a burst of slider changes into one update, then flush the final value if it changed in flight. */
export class FrameTask {
  private dirty = false;
  private stopped = false;
  private pending: Promise<void> | null = null;
  private readonly task: () => Promise<void>;
  private readonly nextFrame: () => Promise<void>;
  constructor(
    task: () => Promise<void>,
    nextFrame: () => Promise<void> = () =>
      new Promise((resolve) => requestAnimationFrame(() => resolve())),
  ) {
    this.task = task;
    this.nextFrame = nextFrame;
  }
  request() {
    if (this.stopped) return Promise.resolve();
    this.dirty = true;
    if (!this.pending) {
      this.pending = this.drain().finally(() => {
        this.pending = null;
      });
    }
    return this.pending;
  }
  private async drain() {
    while (this.dirty && !this.stopped) {
      await this.nextFrame();
      if (this.stopped) break;
      this.dirty = false;
      await this.task();
    }
  }
  dispose() {
    this.stopped = true;
    this.dirty = false;
  }
}

/** Visibility operations must not interleave the SDK's hide-all / show-subset steps. */
export class TaskQueue {
  private tail: Promise<unknown> = Promise.resolve();
  private stopped = false;
  run<T>(task: () => Promise<T>): Promise<T | undefined> {
    const result = this.tail.then(() => (this.stopped ? undefined : task()));
    this.tail = result.catch(() => {});
    return result;
  }
  dispose() {
    this.stopped = true;
  }
}
