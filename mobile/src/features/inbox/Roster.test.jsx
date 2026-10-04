import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  list: null,
  pick: (style, key) => [style].flat(Infinity).filter(Boolean).reduce((v, s) => s[key] ?? v, null),
}));

vi.mock('react-native', () => {
  const plain = ({ style, contentContainerStyle, accessibilityLabel, ...rest }) => ({
    ...rest,
    ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
    'data-font': h.pick(style, 'fontFamily'),
    'data-color': h.pick(style, 'color'),
    'data-size': h.pick(style, 'fontSize'),
    'data-bg': h.pick(style, 'backgroundColor'),
    'data-border': h.pick(style, 'borderColor'),
  });
  const View = ({ children, ...p }) => React.createElement('div', plain(p), children);
  const Text = ({ children, ...p }) => React.createElement('span', plain(p), children);
  const Pressable = ({ children, onPress, hitSlop, ...p }) =>
    React.createElement('button', {
      type: 'button',
      onClick: onPress,
      ...plain(p),
      'data-slop': typeof hitSlop === 'number' ? String(hitSlop) : undefined,
      'data-h': typeof p.style === 'function' ? String(p.style({ pressed: false }).height) : undefined,
    }, children);
  const TextInput = ({ value, onChangeText, accessibilityLabel, placeholder }) =>
    React.createElement('input', {
      value,
      placeholder,
      'aria-label': accessibilityLabel,
      onChange: (e) => onChangeText?.(e.target.value),
    });
  const SectionList = (props) => {
    h.list = props;
    const { sections = [], renderItem, renderSectionHeader, renderSectionFooter, keyExtractor, ListEmptyComponent, ListFooterComponent } = props;
    const el = (c) => (typeof c === 'function' ? React.createElement(c) : c);
    return React.createElement(
      'div',
      { 'data-testid': 'roster' },
      sections.length
        ? sections.map((section) =>
            React.createElement(
              'div',
              { key: section.key, 'data-section': section.key },
              renderSectionHeader({ section }),
              ...section.data.map((item, index) =>
                React.createElement('div', { key: keyExtractor(item, index) }, renderItem({ item, index, section })),
              ),
              renderSectionFooter?.({ section }) ?? null,
            ),
          )
        : el(ListEmptyComponent),
      el(ListFooterComponent),
    );
  };
  return {
    View,
    Text,
    Pressable,
    TextInput,
    SectionList,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    RefreshControl: () => null,
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgElev: '#ffffff', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd',
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
    },
    fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
    mobile: { inputH: 44 },
  }),
}));

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

vi.mock('./InboxRow', () => ({ SEPARATOR_INSET: 52 }));

vi.mock('./InboxSkeleton', () => ({
  InboxSkeleton: () => React.createElement('div', { 'data-testid': 'skeleton' }),
}));

import { space } from '../../theme/tokens';
const haptics = vi.hoisted(() => ({ selection: vi.fn() }));
vi.mock('../../lib/haptics', () => haptics);

import { Roster } from './Roster';

const alpi = { kind: 'profile', id: 'alpi', name: 'alpi', label: 'alpi', preview: 'ready', pinned: true };
const pixel = { kind: 'profile', id: 'pixel', name: 'pixel', label: 'pixel', preview: 'MODEL_OK' };
const abad = { kind: 'workgroup', id: 'wg1', profile: 'mira', label: 'site-hotel-abad', preview: 'hotel abad' };
const roma = { kind: 'workgroup', id: 'wg2', profile: 'mira', label: 'site-roma', preview: 'hotel roma', pinned: true };

const ITEMS = [alpi, pixel, abad, roma];

const plainRow = ({ item }) => React.createElement('span', { 'data-row': item.id }, item.label);

const ADD_ACTIONS = {
  profiles: { label: 'New profile', onPress: vi.fn() },
  workgroups: { label: 'New workgroup', onPress: vi.fn() },
};

function header(label) {
  return screen.getByText(label).closest('div');
}

function sections() {
  return [...document.querySelectorAll('[data-section]')].map((el) => el.getAttribute('data-section'));
}

function rows() {
  return [...document.querySelectorAll('[data-row]')].map((el) => el.getAttribute('data-row'));
}

describe('Roster sections', () => {
  it('draws pinned, profiles and workgroups in that order with mono eyebrow labels', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(sections()).toEqual(['pinned', 'profiles', 'workgroups']);
    expect(rows()).toEqual(['alpi', 'wg2', 'pixel', 'wg1']);
    for (const label of ['PINNED', 'PROFILES', 'WORKGROUPS']) {
      const header = screen.getByText(label);
      expect(header.getAttribute('data-font')).toBe('monoMedium');
      expect(header.getAttribute('data-color')).toBe('#666');
      expect(header.getAttribute('data-size')).toBe('11');
    }
  });

  it('narrows every section with one query and drops the sections left empty', () => {
    const { rerender } = render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    rerender(<Roster items={ITEMS} query="hotel" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(sections()).toEqual(['pinned', 'workgroups']);
    expect(rows()).toEqual(['wg2', 'wg1']);
    expect(screen.queryByText('PROFILES')).toBeNull();
  });

  it('never renders a bare label for a section with no items', () => {
    render(<Roster items={[pixel]} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(sections()).toEqual(['profiles']);
    expect(screen.queryByText('PINNED')).toBeNull();
    expect(screen.queryByText('WORKGROUPS')).toBeNull();
  });

  it('reports what the reader typed', () => {
    const onQueryChange = vi.fn();
    render(<Roster items={ITEMS} query="" onQueryChange={onQueryChange} renderRow={plainRow} searchOpen />);
    fireEvent.change(screen.getByLabelText('Filter list'), { target: { value: 'rom' } });
    expect(onQueryChange).toHaveBeenCalledWith('rom');
  });

  it('mounts no field at all until the surface opens it', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(screen.queryByLabelText('Filter list')).toBeNull();
    expect(screen.getByText('pixel')).toBeTruthy();
  });

  it('fills the filter as a borderless well, like every field', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} searchOpen />);
    const field = screen.getByLabelText('Filter list').parentElement;
    expect(field.getAttribute('data-bg')).toBe('#f1f3f5');
    expect(field.getAttribute('data-border')).toBe('transparent');
  });

  it('calls the entity a profile in the filter, so the @alpi row stays unambiguous', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} searchOpen />);
    expect(screen.getByPlaceholderText('Filter profiles & workgroups')).toBeTruthy();
    expect(screen.queryByPlaceholderText(/alpis/i)).toBeNull();
  });
});

describe('Roster front door', () => {
  const host = { kind: 'profile', id: 'default', name: 'default', label: 'alpi', preview: 'quiet', raw: { name: 'default', is_default: true } };

  it('draws the default profile first, above pinned, with no label and a seam under it', () => {
    render(<Roster items={[pixel, roma, host, alpi]} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(sections()).toEqual(['front', 'pinned', 'profiles']);
    expect(rows()[0]).toBe('default');
    const front = document.querySelector('[data-section="front"]');
    expect(front.textContent).toBe('alpi');
    expect(front.querySelector('[testid="front-seam"]')).toBeTruthy();
  });

  it('drops the seam when the default profile is the only row', () => {
    render(<Roster items={[host]} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(sections()).toEqual(['front']);
    expect(document.querySelector('[testid="front-seam"]')).toBeNull();
  });
});

describe('Roster empty states', () => {
  it('asks for a pairing when no daemon is paired, and hides the filter', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} paired={false} device="phone" />);
    expect(screen.getByText('Not paired')).toBeTruthy();
    expect(screen.getByText('Pair this phone to a daemon and its profiles show up here.')).toBeTruthy();
    expect(screen.queryByLabelText('Filter list')).toBeNull();
  });

  it('says nothing matched instead of claiming the daemon is empty', () => {
    render(<Roster items={ITEMS} query="zzz" onQueryChange={() => {}} renderRow={plainRow} searchOpen />);
    expect(screen.getByText('No matches')).toBeTruthy();
    expect(screen.getByText('Try a different query, or clear it.')).toBeTruthy();
    expect(screen.queryByText('No profiles or workgroups yet')).toBeNull();
    expect(screen.getByLabelText('Filter list')).toBeTruthy();
  });

  it('names the daemon as empty only when it truly has nothing', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={{ profiles: () => {} }} />);
    expect(screen.getByText('No profiles or workgroups yet')).toBeTruthy();
    expect(screen.getByText('Create one to begin.')).toBeTruthy();
  });

  it('tells a reader who cannot create that nothing is shared with this device yet', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} device="phone" />);
    expect(screen.getByText('Nothing shared with this device yet')).toBeTruthy();
    expect(screen.getByText('Ask the host admin to share a profile with this phone.')).toBeTruthy();
    expect(screen.queryByText('Create one to begin.')).toBeNull();
  });

  it('shows the skeleton while the first load is in flight, never an empty verdict', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} loading />);
    expect(screen.getByTestId('skeleton')).toBeTruthy();
    expect(screen.queryByText('No profiles or workgroups yet')).toBeNull();
  });

  it('keeps a spinner under the rows while refreshing a non-empty roster', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} loading />);
    expect(screen.getByTestId('spinner')).toBeTruthy();
    expect(screen.queryByTestId('skeleton')).toBeNull();
  });
});

describe('Roster row seam', () => {
  it('draws one row per item, exactly what renderRow returned', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(rows()).toEqual(['alpi', 'wg2', 'pixel', 'wg1']);
  });

  it('hands renderRow the roster item and a workgroup-safe key', () => {
    const renderRow = vi.fn(plainRow);
    render(<Roster items={[abad]} query="" onQueryChange={() => {}} renderRow={renderRow} />);
    expect(renderRow.mock.calls[0][0].item).toEqual(abad);
    expect(h.list.keyExtractor(abad)).toBe('workgroup:mira/wg1');
    expect(h.list.keyExtractor(pixel)).toBe('profile:pixel');
  });

  it('sizes no row itself — heights vary once headers land in the list', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(h.list.getItemLayout).toBeUndefined();
  });

  it('ends the scroll on one gutter of breathing room, not on chrome clearance', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(h.list.contentContainerStyle.paddingBottom).toBe(space.s9);
  });
});

describe('Roster section add', () => {
  it('puts a labelled + on the profiles and workgroups headings', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={ADD_ACTIONS} />);
    expect(header('PROFILES').querySelector('[aria-label="New profile"] [data-icon="plus"]')).toBeTruthy();
    expect(header('WORKGROUPS').querySelector('[aria-label="New workgroup"] [data-icon="plus"]')).toBeTruthy();
  });

  it('leaves the pinned heading bare — a pin is not something you create', () => {
    render(
      <Roster
        items={ITEMS}
        query=""
        onQueryChange={() => {}}
        renderRow={plainRow}
        addActions={{ ...ADD_ACTIONS, pinned: { label: 'New pin', onPress: () => {} } }}
      />,
    );
    expect(header('PINNED').querySelector('button')).toBeNull();
    expect(screen.queryByLabelText('New pin')).toBeNull();
  });

  it('keeps every heading bare when no add action is handed in', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    for (const label of ['PINNED', 'PROFILES', 'WORKGROUPS']) {
      expect(header(label).querySelector('button')).toBeNull();
    }
  });

  it('calls the action of the heading that was pressed', () => {
    render(<Roster items={ITEMS} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={ADD_ACTIONS} />);
    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(ADD_ACTIONS.workgroups.onPress).toHaveBeenCalledTimes(1);
    expect(ADD_ACTIONS.profiles.onPress).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('New profile'));
    expect(ADD_ACTIONS.profiles.onPress).toHaveBeenCalledTimes(1);
  });
});

describe('Roster creation reachability', () => {
  const addActions = () => ({
    profiles: { label: 'New profile', onPress: vi.fn() },
    workgroups: { label: 'New workgroup', onPress: vi.fn() },
  });

  it('holds the workgroups heading on a daemon with none, so the first workgroup can be created', () => {
    const actions = addActions();
    render(<Roster items={[pixel]} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={actions} />);
    expect(sections()).toEqual(['profiles', 'workgroups']);
    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(actions.workgroups.onPress).toHaveBeenCalledTimes(1);
  });

  it('holds both headings when every row is pinned', () => {
    const actions = addActions();
    render(<Roster items={[alpi, roma]} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={actions} />);
    expect(sections()).toEqual(['pinned', 'profiles', 'workgroups']);
    expect(rows()).toEqual(['alpi', 'wg2']);
    fireEvent.click(screen.getByLabelText('New profile'));
    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(actions.profiles.onPress).toHaveBeenCalledTimes(1);
    expect(actions.workgroups.onPress).toHaveBeenCalledTimes(1);
  });

  it('holds both headings on an empty daemon and still names it empty', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={addActions()} />);
    expect(sections()).toEqual(['profiles', 'workgroups']);
    expect(screen.getByLabelText('New profile')).toBeTruthy();
    expect(screen.getByLabelText('New workgroup')).toBeTruthy();
    expect(screen.getByText('No profiles or workgroups yet')).toBeTruthy();
  });

  it('holds no heading for a reader who cannot create', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} />);
    expect(sections()).toEqual([]);
    expect(screen.getByText('Nothing shared with this device yet')).toBeTruthy();
  });

  it('drops the held headings while a filter is on, so a miss reads as a miss', () => {
    render(
      <Roster items={ITEMS} query="zzz" onQueryChange={() => {}} renderRow={plainRow} addActions={addActions()} searchOpen />,
    );
    expect(sections()).toEqual([]);
    expect(screen.getByText('No matches')).toBeTruthy();
    expect(screen.queryByLabelText('New workgroup')).toBeNull();
  });

  it('shows the skeleton over the held headings while the first load is in flight', () => {
    render(<Roster items={[]} query="" onQueryChange={() => {}} renderRow={plainRow} addActions={addActions()} loading />);
    expect(screen.getByTestId('skeleton')).toBeTruthy();
    expect(screen.queryByText('No profiles or workgroups yet')).toBeNull();
    expect(screen.getByLabelText('New workgroup')).toBeTruthy();
  });

  it('tells the truth while the daemon is down and when the roster failed to load', () => {
    const onRefresh = vi.fn();
    const { rerender } = render(<Roster items={[]} paired daemonDown onRefresh={onRefresh} />);
    expect(screen.getByText('Daemon unreachable')).toBeTruthy();
    expect(screen.queryByText('No profiles or workgroups yet')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    rerender(<Roster items={[]} paired error={new Error('read timeout')} onRefresh={onRefresh} />);
    expect(screen.getByText("Couldn't load the roster")).toBeTruthy();
    expect(screen.getByText('read timeout')).toBeTruthy();
  });
});

describe('Roster section add targets', () => {
  it('pads the New profile and New workgroup buttons to the 44 pt minimum', () => {
    render(<Roster items={[]} paired addActions={{ profiles: { label: 'New profile', onPress: () => {} }, workgroups: { label: 'New workgroup', onPress: () => {} } }} />);
    for (const name of ['New profile', 'New workgroup']) {
      const button = screen.getByLabelText(name);
      expect(Number(button.getAttribute('data-h')) + Number(button.getAttribute('data-slop')) * 2).toBe(44);
      expect(button.getAttribute('accessibilityRole')).toBe('button');
    }
  });
});

describe('Roster pull to refresh', () => {
  it('hands the pull to the screen, which owns the haptic tick and the failure message', () => {
    haptics.selection.mockClear();
    const onRefresh = vi.fn();
    render(<Roster items={[]} paired onRefresh={onRefresh} />);
    h.list.refreshControl.props.onRefresh();
    expect(haptics.selection).not.toHaveBeenCalled();
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
