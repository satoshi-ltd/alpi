export function quiet(promise) {
  promise.catch(() => {});
  return promise;
}
