/** Reject corrupt/truncated imports before allocating the whole IFC in memory.
 * Native STEP exports end with this terminator, optionally followed by comments.
 */
export async function validateStepFile(file: Blob) {
  const [head, tail] = await Promise.all([
    file.slice(0, 4096).text(),
    file.slice(Math.max(0, file.size - 65536)).text(),
  ]);
  if (!head.includes('ISO-10303-21;'))
    throw new Error(
      'This is not a STEP IFC file. Export an uncompressed .ifc file.',
    );
  if (!tail.includes('END-ISO-10303-21;'))
    throw new Error(
      'The IFC end marker is missing. The file may be truncated; export a complete .ifc file.',
    );
}
