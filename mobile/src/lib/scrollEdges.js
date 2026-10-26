export function scrollEdges({ contentOffset, contentSize, layoutMeasurement }) {
  const overflow = contentSize.width - layoutMeasurement.width;
  return { left: contentOffset.x > 1, right: overflow > 1 && contentOffset.x < overflow - 1 };
}
