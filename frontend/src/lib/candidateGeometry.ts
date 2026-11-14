import type {
  CandidateImage,
  ImageCandidate,
} from '../contracts/ImageCandidateResponse';

/** Match the imported <image>'s centered xMidYMid meet fit in DrawingArtwork. */
export function candidateBounds(
  candidate: ImageCandidate,
  image: Pick<CandidateImage, 'width' | 'height'>,
): [number, number, number, number] {
  if (!(image.width > 0 && image.height > 0))
    throw new Error('Candidate image dimensions must be positive.');
  const scale = Math.min(1050 / image.width, 730 / image.height);
  const offsetX = 25 + (1050 - image.width * scale) / 2;
  const offsetY = 25 + (730 - image.height * scale) / 2;
  const [xmin, ymin] = candidate.geometry.minimum;
  const [xmax, ymax] = candidate.geometry.maximum;
  return [
    offsetX + xmin * scale,
    offsetY + ymin * scale,
    (xmax - xmin) * scale,
    (ymax - ymin) * scale,
  ];
}
