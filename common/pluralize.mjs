export function pluralize(count, singular, plural) {
  return Number(count) === 1 ? singular : plural ?? `${singular}s`;
}
