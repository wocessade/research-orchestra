export function BrandMark() {
  return (
    <div className="brand-mark" aria-label="Bogda Console">
      <svg className="brand-mark__ridge" viewBox="0 0 88 46" role="img" aria-label="博格达山峰标志">
        <path d="M4 39 21 25l9 6L45 8l13 19 8-6 18 18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        <path data-testid="bogda-contours" aria-hidden="true" d="M9 40c13-5 22-4 33-1 14 4 24 4 38-1M18 43c12-3 22-2 32 0" fill="none" stroke="currentColor" strokeWidth="1" opacity=".45" />
      </svg>
      <span><strong>Bogda</strong><small>Research observatory</small></span>
    </div>
  );
}
