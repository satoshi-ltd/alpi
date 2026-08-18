export function postsOf(transcript) {
  const posts = transcript?.posts ?? transcript?.messages ?? [];
  return Array.isArray(posts) ? posts : [];
}

function postKey(post) {
  return `${post?.from_pubkey}|${post?.body}`;
}

export function unlandedPosts(optimistic, transcript) {
  const landed = new Set(postsOf(transcript).map(postKey));
  return (optimistic ?? []).filter((post) => !landed.has(postKey(post)));
}
