export function isComposing(event) {
  return Boolean(event?.nativeEvent?.isComposing || event?.isComposing || event?.keyCode === 229);
}
