import { describe, expect, it } from 'vitest';

import { matchesQuery, rosterIsEmpty, rosterSections } from './roster';

const alpi = { kind: 'profile', id: 'alpi', name: 'alpi', label: 'alpi', preview: 'ready', pinned: true };
const pixel = { kind: 'profile', id: 'pixel', name: 'pixel', label: 'pixel', preview: 'MODEL_OK' };
const mira = { kind: 'profile', id: 'mira', name: 'mira', label: 'mira', preview: 'orden lista' };
const abad = { kind: 'workgroup', id: 'wg1', label: 'site-hotel-abad-v23', preview: "Workgroup for hotel 'hotel-abad'" };
const roma = { kind: 'workgroup', id: 'wg2', label: 'site-roma-nueve-dos', preview: 'Workgroup for hotel', pinned: true };

const all = [alpi, pixel, mira, abad, roma];

describe('rosterSections', () => {
  it('groups pinned first, then profiles, then workgroups', () => {
    const sections = rosterSections(all, '');
    expect(sections.map((s) => s.key)).toEqual(['pinned', 'profiles', 'workgroups']);
    expect(sections[0].data).toEqual([alpi, roma]);
    expect(sections[1].data).toEqual([pixel, mira]);
    expect(sections[2].data).toEqual([abad]);
  });

  it('never lists a pinned item twice', () => {
    const ids = rosterSections(all, '').flatMap((s) => s.data.map((i) => i.id));
    expect(ids).toEqual([...new Set(ids)]);
  });

  it('drops empty sections instead of rendering a bare label', () => {
    expect(rosterSections([pixel, mira], '').map((s) => s.key)).toEqual(['profiles']);
    expect(rosterSections([], '')).toEqual([]);
    expect(rosterIsEmpty(rosterSections([], ''))).toBe(true);
  });

  it('filters every section by the query and keeps the surviving order', () => {
    const sections = rosterSections(all, 'hotel');
    expect(sections.map((s) => s.key)).toEqual(['pinned', 'workgroups']);
    expect(sections[0].data).toEqual([roma]);
    expect(sections[1].data).toEqual([abad]);
  });

  it('matches on preview text, not just the name', () => {
    expect(rosterSections(all, 'MODEL_OK').map((s) => s.data.map((i) => i.id))).toEqual([['pixel']]);
  });
});

describe('rosterSections creation reachability', () => {
  const CREATABLE = { keepEmpty: ['profiles', 'workgroups'] };

  it('keeps an empty creatable section, so a daemon with no workgroups still has a heading to create from', () => {
    const sections = rosterSections([pixel, mira], '', CREATABLE);
    expect(sections.map((s) => s.key)).toEqual(['profiles', 'workgroups']);
    expect(sections[1].data).toEqual([]);
  });

  it('keeps both creatable headings when the daemon holds nothing at all', () => {
    expect(rosterSections([], '', CREATABLE).map((s) => s.key)).toEqual(['profiles', 'workgroups']);
  });

  it('keeps both creatable headings when every item is pinned', () => {
    const sections = rosterSections([alpi, roma], '', CREATABLE);
    expect(sections.map((s) => s.key)).toEqual(['pinned', 'profiles', 'workgroups']);
    expect(sections[0].data).toEqual([alpi, roma]);
    expect(sections[1].data).toEqual([]);
    expect(sections[2].data).toEqual([]);
  });

  it('never keeps an empty pinned section — a pin is not something you create', () => {
    const sections = rosterSections([pixel], '', { keepEmpty: ['pinned', 'profiles', 'workgroups'] });
    expect(sections.map((s) => s.key)).toEqual(['profiles', 'workgroups']);
  });

  it('drops the kept headings while a query is filtering, so a miss still reads as a miss', () => {
    expect(rosterSections(all, 'zzz', CREATABLE)).toEqual([]);
    expect(rosterSections(all, '#site-roma', CREATABLE).map((s) => s.key)).toEqual(['pinned']);
  });

  it('still calls a roster of bare headings empty', () => {
    expect(rosterIsEmpty(rosterSections([], '', CREATABLE))).toBe(true);
    expect(rosterIsEmpty(rosterSections([alpi, roma], '', CREATABLE))).toBe(false);
  });
});

describe('matchesQuery', () => {
  it('is case-insensitive and ignores surrounding blanks', () => {
    expect(matchesQuery(pixel, '  PIXEL ')).toBe(true);
    expect(matchesQuery(pixel, 'PiXeL')).toBe(true);
  });

  it('treats an empty query as match-all', () => {
    for (const q of ['', '   ', null, undefined]) expect(matchesQuery(pixel, q)).toBe(true);
  });

  it('does not match an unrelated needle', () => {
    expect(matchesQuery(pixel, 'zzz')).toBe(false);
  });

  it('ignores a leading @ or # so a typed mention still matches', () => {
    expect(matchesQuery(pixel, '@pixel')).toBe(true);
    expect(matchesQuery(abad, '#site-hotel')).toBe(true);
    expect(rosterSections(all, '#site-roma').map((s) => s.data.map((i) => i.id))).toEqual([['wg2']]);
  });

  it('strips only the leading marker, not one inside the needle', () => {
    expect(matchesQuery({ label: 'a#b' }, '#a#b')).toBe(true);
    expect(matchesQuery({ label: 'ab' }, 'a#b')).toBe(false);
  });
});
