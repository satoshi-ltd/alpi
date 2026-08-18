import { describe, expect, it } from 'vitest';

import { postsOf, unlandedPosts } from './optimisticPosts.js';

const mine = { seq: -1, from_pubkey: 'local:doc', body: 'hola', pending: true };
const landed = { seq: 7, from_pubkey: 'local:doc', body: 'hola' };

describe('postsOf', () => {
  it('reads either transcript shape and tolerates a failed read', () => {
    expect(postsOf({ posts: [landed] })).toEqual([landed]);
    expect(postsOf({ messages: [landed] })).toEqual([landed]);
    expect(postsOf(null)).toEqual([]);
    expect(postsOf({ posts: 'nope' })).toEqual([]);
  });
});

describe('unlandedPosts', () => {
  it('keeps an optimistic post the transcript does not carry yet', () => {
    expect(unlandedPosts([mine], { posts: [] })).toEqual([mine]);
  });

  it('keeps everything when the refresh failed or never resolved', () => {
    expect(unlandedPosts([mine], null)).toEqual([mine]);
  });

  it('drops the optimistic copy once the same author and body are persisted', () => {
    expect(unlandedPosts([mine], { posts: [landed] })).toEqual([]);
  });

  it('keeps a same-body post from another author', () => {
    expect(unlandedPosts([mine], { posts: [{ ...landed, from_pubkey: 'peer' }] })).toEqual([mine]);
  });
});
