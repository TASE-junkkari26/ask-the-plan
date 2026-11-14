import { Component } from 'react';
import type { ReactNode } from 'react';

/** A missing lazy viewer chunk must leave the source picker usable. */
export class ViewerBoundary extends Component<
  { children: ReactNode; onBrowse: () => void },
  { error: string | null }
> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: unknown) {
    return {
      error:
        error instanceof Error
          ? error.message
          : 'The viewer module could not be loaded.',
    };
  }
  render() {
    return this.state.error ? (
      <div className="ifc-module-loading" role="alert">
        <div>
          <strong>The 3D viewer could not load.</strong>
          <p>{this.state.error}</p>
          <button className="secondary-button" onClick={this.props.onBrowse}>
            Choose another source
          </button>
        </div>
      </div>
    ) : (
      this.props.children
    );
  }
}
