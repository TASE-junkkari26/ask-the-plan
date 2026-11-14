/** Signals that the native geometry runtime is poisoned and needs a fresh worker. */
export class NativeIfcConversionError extends Error {
  name = 'NativeIfcConversionError';
}

export function isNativeIfcAbort(error: unknown) {
  return (
    error instanceof WebAssembly.RuntimeError ||
    (error instanceof Error &&
      /Aborted\(|memory access out of bounds|table index is out of bounds/i.test(
        error.message,
      ))
  );
}

/** Native aborts poison WASM. At most one isolated, explicitly partial recovery is allowed. */
export async function convertWithGeometryRecovery<T>(
  attempt: (recoverGeometry: boolean) => Promise<T>,
  alreadyRecovering: boolean,
  checkActive: () => void,
  onRecovery: () => void,
): Promise<T> {
  try {
    return await attempt(alreadyRecovering);
  } catch (error) {
    if (!(error instanceof NativeIfcConversionError)) throw error;
    if (alreadyRecovering) throw recoveryFailure(error);
    checkActive();
    onRecovery();
    try {
      return await attempt(true);
    } catch (recoveryError) {
      if (recoveryError instanceof NativeIfcConversionError)
        throw recoveryFailure(recoveryError);
      throw recoveryError;
    }
  }
}

function recoveryFailure(cause: Error) {
  return new Error(
    'The IFC geometry could not be recovered safely. Re-export the source model or try a device with more available memory.',
    { cause },
  );
}
