export const SCIENTIFIC_REVIEW_ID = "scientific-review";

export function scientificReviewPath(runId: string) {
  return `/runs/${runId}#${SCIENTIFIC_REVIEW_ID}`;
}
