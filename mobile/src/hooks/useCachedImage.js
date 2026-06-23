import { useEffect, useState } from 'react';

import { imageCacheKey } from '../lib/attachments';

const imageCache = new Map();
const MAX_CACHED_IMAGES = 32;

function rememberImage(key, value) {
  imageCache.delete(key);
  imageCache.set(key, value);
  while (imageCache.size > MAX_CACHED_IMAGES) {
    imageCache.delete(imageCache.keys().next().value);
  }
}

export function clearImageCache() {
  imageCache.clear();
}

export function useCachedImage(call, endpoint, profile, path) {
  const cacheKey = imageCacheKey(endpoint?.id, profile, path);
  const [state, setState] = useState(() => ({
    key: cacheKey,
    uri: imageCache.get(cacheKey) || null,
    err: null,
  }));

  useEffect(() => {
    const cached = imageCache.get(cacheKey) || null;
    if (cached) rememberImage(cacheKey, cached);
    setState({ key: cacheKey, uri: cached, err: null });
    if (cached || !endpoint || !profile || !path) return undefined;
    let alive = true;
    call('host.attachments.fetch', { profile, path })
      .then((r) => {
        const u = r?.data_base64 ? `data:${r.mime};base64,${r.data_base64}` : null;
        if (u) rememberImage(cacheKey, u);
        if (!alive) return;
        setState({ key: cacheKey, uri: u || null, err: u ? null : 'empty response' });
      })
      .catch((e) => {
        if (alive) setState({ key: cacheKey, uri: null, err: String(e?.message || e) });
      });
    return () => { alive = false; };
  }, [cacheKey, call]);

  if (state.key !== cacheKey) {
    return { uri: imageCache.get(cacheKey) || null, err: null };
  }
  return { uri: state.uri, err: state.err };
}
