import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  pathname: '/wg/alpha',
  canGoBack: vi.fn(() => true),
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ canGoBack: h.canGoBack }),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        'data-style': JSON.stringify(h.flatStyle(style)),
      },
      children,
    );
  const Text = ({ children, style, numberOfLines, ...p }) =>
    React.createElement('span', { ...p, 'data-style': JSON.stringify(h.flatStyle(style)) }, children);
  const Pressable = ({ children, onPress, hitSlop, style, accessibilityLabel, accessibilityState, ...p }) => {
    const body = children instanceof Function ? children({ pressed: false }) : children;
    const resolved = style instanceof Function ? style({ pressed: false }) : style;
    return React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'aria-label': accessibilityLabel,
        'aria-expanded': accessibilityState?.expanded === undefined ? undefined : String(accessibilityState.expanded),
        'data-hitslop': hitSlop === undefined ? undefined : String(hitSlop),
        'data-style': JSON.stringify(h.flatStyle(resolved)),
        ...p,
      },
      body,
    );
  };
  const ScrollView = ({ children, horizontal, directionalLockEnabled, showsHorizontalScrollIndicator, style, contentContainerStyle, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        'data-scroll': horizontal ? 'horizontal' : 'vertical',
        'data-locked': String(!!directionalLockEnabled),
        'data-indicator': String(showsHorizontalScrollIndicator !== false),
        'data-style': JSON.stringify(h.flatStyle(style)),
        'data-content-style': JSON.stringify(h.flatStyle(contentContainerStyle)),
      },
      children,
    );
  const Modal = ({ children, visible, onRequestClose }) => (visible ? React.createElement('div', { 'data-modal': 'open', onKeyDown: onRequestClose }, children) : null);
  return { View, Text, Pressable, ScrollView, Modal, useWindowDimensions: () => ({ width: 390, height: 800 }) };
});

vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) }));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
      bg: '#fff', bgElev: '#fafafa', line: '#eee', line2: '#ddd', selected: '#eee', pressed: '#e0e0e0', accent: '#c90', warning: '#e08a3c', danger: '#c14545',
    },
    fonts: {
      sans: { regular: 'r', medium: 'm', semibold: 's' },
      mono: 'mono',
      monoMedium: 'monoMedium',
    },
    fontSizes: { xs: 12, sm: 14, md: 15, lg: 16, xl: 20, display: 28 },
    shadow: { popover: { shadowOpacity: 0.1 } },
  }),
}));

vi.mock('../../components/Fold', () => ({ Fold: ({ shape, color, size, state, phase, active }) => React.createElement('span', { 'data-shape': shape ?? 'diamond', 'data-color': color, 'data-size': size, 'data-state': state ?? '', 'data-phase': phase ? phase.join('/') : '', 'data-active': active ?? '' }) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', {}, name) }));

import { PaneContext } from '../../nav/PaneContext';
import { BACK_BLEED, BACK_INK_INSET, CHROME_BTN, PANE_PAD_X, TOGGLE_BLEED, tapSlop } from '../../lib/panes';
import { fonts, iconSizes, mobile, radii, space } from '../../theme/tokens';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { nameTone } from '../../../../common/name.mjs';
import { ChatHeader, headerMenuActions, PHONE_HEADER_H } from './ChatHeader';

function inTwoPane(node) {
  return render(<PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>);
}

function headerStyle(container) {
  return JSON.parse(container.firstChild.getAttribute('data-style'));
}

function styleOf(el) {
  return JSON.parse(el.getAttribute('data-style'));
}

function labels(actions) {
  return actions.filter((a) => !a.divider).map((a) => a.label);
}

beforeEach(() => {
  h.pathname = '/wg/alpha';
  h.canGoBack.mockClear().mockReturnValue(true);
});

describe('ChatHeader profile fold', () => {
  it('draws the profile fold at header size in the accent', () => {
    const { container } = render(<ChatHeader kind="profile" accent="#3899e2" shape="shield" title="@doc" />);
    const fold = container.querySelector('[data-shape]');
    expect(fold.getAttribute('data-shape')).toBe('shield');
    expect(fold.getAttribute('data-color')).toBe('#3899e2');
    expect(fold.getAttribute('data-size')).toBe(String(MARK_SIZES.header));
  });

  it('draws the legacy diamond when the profile never chose a fold', () => {
    const { container } = render(<ChatHeader kind="profile" accent="#3899e2" title="@doc" />);
    expect(container.querySelector('[data-shape]').getAttribute('data-shape')).toBe('diamond');
  });

  it('draws the honeycomb in the hub colour for a workgroup, whatever fold the profile has', () => {
    const { container } = render(<ChatHeader kind="workgroup" shape="shield" accent="#6572e4" title="alpha" />);
    const fold = container.querySelector('[data-shape]');
    expect(fold.getAttribute('data-shape')).toBe('honeycomb');
    expect(fold.getAttribute('data-color')).toBe('#6572e4');
    expect(fold.getAttribute('data-state')).toBe('');
  });

  it('hands the run state and progress to the workgroup mark with the hub colour', () => {
    const { container } = render(<ChatHeader kind="workgroup" accent="#6572e4" title="alpha" mark={{ state: 'running', phase: [1, 3], owner: 'lingo' }} />);
    const fold = container.querySelector('[data-shape]');
    expect(fold.getAttribute('data-state')).toBe('running');
    expect(fold.getAttribute('data-phase')).toBe('1/3');
    expect(fold.getAttribute('data-color')).toBe('#6572e4');
  });

  it('lights the workgroup mark in the working profile colour when one is given, never a profile mark', () => {
    const wg = render(<ChatHeader kind="workgroup" accent="#6572e4" markColor="#3ec173" title="alpha" mark={{ state: 'running', phase: [1, 3], owner: 'lingo' }} />);
    expect(wg.container.querySelector('[data-shape]').getAttribute('data-color')).toBe('#3ec173');
    wg.unmount();
    const profile = render(<ChatHeader kind="profile" shape="heart" accent="#6572e4" markColor="#3ec173" title="doc" />);
    expect(profile.container.querySelector('[data-shape]').getAttribute('data-color')).toBe('#6572e4');
  });

  it('draws a paused mark as paused whatever state it is handed, and greys its name', () => {
    for (const kind of ['workgroup', 'profile']) {
      const { container } = render(<ChatHeader kind={kind} named accent="#6572e4" title="alpha" paused mark={{ state: 'working' }} />);
      expect(container.querySelector('[data-shape]').getAttribute('data-state')).toBe('paused');
      expect(styleOf(screen.getByText('alpha')).color).toBe('#666');
      cleanup();
    }
  });
});

describe('ChatHeader name title', () => {
  it('draws the name in the name face at the 20 pt title rung, a step darker than its mark on a light ground', () => {
    render(<ChatHeader kind="profile" named accent="#3899e2" title="@doc" />);
    const name = styleOf(screen.getByText('@doc'));
    expect(name.fontFamily).toBe(fonts.name);
    expect(name.color).toBe(nameTone('#3899e2', '#fff'));
    expect(name.fontSize).toBe(20);
  });

  it('draws a workgroup name in the name face in neutral ink, never the hub tone', () => {
    render(<ChatHeader kind="workgroup" named accent="#3899e2" title="alpha" />);
    const name = styleOf(screen.getByText('alpha'));
    expect(name.fontFamily).toBe(fonts.name);
    expect(name.color).toBe('#000');
  });

  it('keeps plain Geist for placeholder headers that are not named', () => {
    render(<ChatHeader kind="profile" accent="#666" title="@doc" meta="loading…" />);
    expect(styleOf(screen.getByText('@doc')).fontFamily).toBe('s');
  });

  it('keeps plain Geist when there is no accent', () => {
    render(<ChatHeader kind="workgroup" named title="#alpha" />);
    expect(styleOf(screen.getByText('#alpha')).fontFamily).toBe('s');
  });
});

describe('ChatHeader back chevron', () => {
  it('renders the chevron outside any pane provider', () => {
    render(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
    expect(screen.getByText('#alpha')).toBeTruthy();
  });

  it('drops the chevron at a pane root in two-pane mode', () => {
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
    expect(screen.getByText('#alpha')).toBeTruthy();
  });

  it('keeps the chevron on a drilled screen in two-pane mode', () => {
    h.pathname = '/wg/alpha/settings';
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('keeps the chevron on a cold deep link with no history — useBack replaces its way out', () => {
    h.pathname = '/wg/alpha/settings';
    h.canGoBack.mockReturnValue(false);
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
    expect(h.canGoBack).not.toHaveBeenCalled();
  });

  it('fires onBack when the chevron is pressed on a phone', () => {
    const onBack = vi.fn();
    render(<ChatHeader kind="workgroup" title="#alpha" onBack={onBack} />);
    screen.getByText('back').parentElement.click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});

describe('ChatHeader gutter', () => {
  it('keeps the pane edge on two panes and seats the phone controls 8 pt in, so their 44 pt circles centre the title', () => {
    const two = inTwoPane(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(headerStyle(two.container).paddingHorizontal).toBe(PANE_PAD_X);
    two.unmount();
    const { container } = render(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(headerStyle(container).paddingHorizontal).toBe(space.s3);
  });
});

describe('ChatHeader descenders', () => {
  it.each([
    ['two-pane', inTwoPane],
    ['the phone', render],
  ])('leaves the title room for a descender on %s — Android clips what web lets overflow', (_, mount) => {
    mount(<ChatHeader kind="profile" title="lingo" />);
    const style = JSON.parse(screen.getByText('lingo').getAttribute('data-style'));
    expect(style.lineHeight).toBeGreaterThan(style.fontSize);
  });
});

describe('ChatHeader title scale', () => {
  it('keeps the 20 pt title under two panes', () => {
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(styleOf(screen.getByText('#alpha')).fontSize).toBe(20);
  });

  it('sets the phone title at the same 20 pt in a 64 pt centred header', () => {
    const { container } = render(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(styleOf(screen.getByText('#alpha')).fontSize).toBe(20);
    expect(headerStyle(container).minHeight).toBe(PHONE_HEADER_H);
    expect(PHONE_HEADER_H).toBe(56);
  });
});

describe('ChatHeader phone anatomy', () => {
  const DETAILS = {
    model: 'deepseek-v4.1-flash',
    modelId: 'openrouter/deepseek/deepseek-v4.1-flash',
    context: { value: '36K', tail: '/1.0M', pct: 0.04 },
    cost: { value: '$0.07', tail: '/$1.00', pct: 0.07 },
  };

  it('draws one 56 pt row with the chip centred between two 88 pt side columns and no model line', () => {
    const { container } = render(<ChatHeader kind="profile" named accent="#3899e2" title="doc" details={DETAILS} onBack={() => {}} onMore={() => {}} />);
    expect(PHONE_HEADER_H).toBe(56);
    expect(headerStyle(container).minHeight).toBe(56);
    const [left, centre, right] = container.firstChild.children;
    expect(styleOf(left).width).toBe(88);
    expect(styleOf(right).width).toBe(88);
    expect(styleOf(centre).justifyContent).toBe('center');
    expect(left.contains(screen.getByLabelText('Back'))).toBe(true);
    expect(right.contains(screen.getByLabelText('More'))).toBe(true);
    expect(centre.contains(screen.getByLabelText('doc, profile details'))).toBe(true);
    expect(screen.queryByText('deepseek-v4.1-flash')).toBeNull();
    expect(document.querySelector('[testid="header-model"]')).toBeNull();
  });

  it('keeps a header extra such as the read-aloud wave beside the chip, out of the 88 pt action column', () => {
    const { container } = render(<ChatHeader kind="profile" named accent="#3899e2" title="doc" details={DETAILS} right={<span data-testid="wave" />} onMore={() => {}} />);
    const [, centre, right] = container.firstChild.children;
    expect(centre.contains(screen.getByTestId('wave'))).toBe(true);
    expect(right.contains(screen.getByTestId('wave'))).toBe(false);
  });

  it('sizes the chip to a 44 pt target with a pill radius and the mark at 28', () => {
    const { container } = render(<ChatHeader kind="profile" named accent="#3899e2" title="doc" details={DETAILS} />);
    const chip = screen.getByLabelText('doc, profile details');
    expect(styleOf(chip).minHeight).toBe(44);
    expect(styleOf(chip).borderRadius).toBe(radii.pill);
    expect(chip.querySelector('[data-size]').getAttribute('data-size')).toBe('28');
    expect(container.querySelectorAll('[data-modal]')).toHaveLength(0);
  });

  it('opens the details popover on a chip tap and closes it from the backdrop or Back', () => {
    render(<ChatHeader kind="profile" named accent="#3899e2" title="doc" details={DETAILS} />);
    const chip = screen.getByLabelText('doc, profile details');
    expect(chip.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(chip);
    expect(document.querySelector('[data-modal="open"]')).toBeTruthy();
    expect(chip.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('Model')).toBeTruthy();
    expect(screen.getByText('deepseek-v4.1-flash')).toBeTruthy();
    expect(document.querySelector('[testid="details-model-id"]').textContent).toBe('openrouter/deepseek/deepseek-v4.1-flash');
    expect(screen.getByText('Context')).toBeTruthy();
    expect(screen.getByText('Cost today')).toBeTruthy();
    expect(screen.getByLabelText('Context window')).toBeTruthy();
    fireEvent.click(document.querySelector('[testid="details-backdrop"]'));
    expect(document.querySelector('[data-modal="open"]')).toBeNull();
    fireEvent.click(chip);
    fireEvent.keyDown(document.querySelector('[data-modal="open"]'));
    expect(document.querySelector('[data-modal="open"]')).toBeNull();
  });

  it('omits the rows the profile has no data for', () => {
    render(<ChatHeader kind="profile" named accent="#3899e2" title="doc" details={{ model: 'm', modelId: null, context: null, cost: null }} />);
    fireEvent.click(screen.getByLabelText('doc, profile details'));
    expect(screen.queryByText('Context')).toBeNull();
    expect(screen.queryByText('Cost today')).toBeNull();
    expect(document.querySelector('[testid="details-model-id"]')).toBeNull();
  });

  it('keeps the meters off the phone header', () => {
    render(<ChatHeader kind="profile" title="doc" details={DETAILS} meta={<span data-meta="context">20K</span>} />);
    expect(document.querySelector('[data-meta]')).toBeNull();
  });

  it('fades the stream under the header instead of a rule', () => {
    const { container } = render(<ChatHeader kind="profile" title="doc" />);
    const styles = [...container.querySelectorAll('div')].map(styleOf);
    expect(styles.some((st) => st.borderBottomWidth)).toBe(false);
    expect(styles.some((st) => st.position === 'absolute' && st.top === '100%')).toBe(true);
  });
});

describe('ChatHeader box', () => {
  it('draws every phone control as a 44 pt circle, the touch target itself', () => {
    render(<ChatHeader kind="profile" title="doc" onBack={() => {}} onPickSession={() => {}} onMore={() => {}} />);
    for (const label of ['Back', 'Sessions', 'More']) {
      const style = styleOf(screen.getByLabelText(label));
      expect(style.height).toBe(mobile.tap);
      expect(style.borderRadius).toBe(999);
    }
  });
});

describe('ChatHeader seam', () => {
  it.each([['two panes', true], ['the phone', false]])('ends on its seam with no accent stripe in %s', (_, two) => {
    const header = <ChatHeader kind="workgroup" title="#alpha" accent="#abc123" />;
    const { container } = two ? inTwoPane(header) : render(header);
    const stripe = [...container.querySelectorAll('div')]
      .map(styleOf)
      .find((s) => s.position === 'absolute' && s.backgroundColor === '#abc123');
    expect(stripe).toBeUndefined();
  });

  it('seats the session and more controls on the title line, so the meta strip keeps the full width', () => {
    const { container } = inTwoPane(
      <ChatHeader kind="profile" title="etxea" onPickSession={() => {}} onMore={() => {}} />,
    );
    const title = screen.getByText('etxea');
    const clock = screen.getByLabelText('Sessions');
    expect(title.parentElement.parentElement.contains(clock)).toBe(true);
    expect(styleOf(container.firstChild).alignItems).toBe('flex-start');
  });
});

describe('ChatHeader session trigger', () => {
  it('keeps the same icon-only trigger under two panes, never a labelled control', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} />);
    expect(screen.getByText('history')).toBeTruthy();
    expect(screen.queryByText('Sessions')).toBeNull();
    expect(screen.getByLabelText('Sessions')).toBeTruthy();
  });

  it('keeps the icon-only trigger on the phone', () => {
    render(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} />);
    expect(screen.queryByText('Sessions')).toBeNull();
    expect(screen.getByText('history')).toBeTruthy();
    expect(screen.getByLabelText('Sessions')).toBeTruthy();
  });

  it('fires onPickSession from either trigger', () => {
    const onPickSession = vi.fn();
    const phone = render(<ChatHeader kind="profile" title="doc" onPickSession={onPickSession} />);
    screen.getByLabelText('Sessions').click();
    phone.unmount();
    inTwoPane(<ChatHeader kind="profile" title="doc" onPickSession={onPickSession} />);
    screen.getByLabelText('Sessions').click();
    expect(onPickSession).toHaveBeenCalledTimes(2);
  });
});

describe('ChatHeader failed jobs', () => {
  it('marks the menu button and says how many jobs failed', () => {
    render(<ChatHeader kind="profile" title="doc" onMore={() => {}} failedJobs={2} />);
    expect(screen.getByLabelText('More, 2 jobs failed')).toBeTruthy();
    expect(document.querySelector('[testid="failed-jobs-dot"]')).toBeTruthy();
    cleanup();
    render(<ChatHeader kind="profile" title="doc" onMore={() => {}} failedJobs={1} />);
    expect(screen.getByLabelText('More, 1 job failed')).toBeTruthy();
  });

  it('hands the menu the trigger rect so a fold can anchor its popover there', () => {
    HTMLElement.prototype.measureInWindow = (cb) => cb(796, 3, 44, 44);
    const onMore = vi.fn();
    render(<ChatHeader kind="profile" title="doc" onMore={onMore} />);
    fireEvent.click(screen.getByLabelText('More'));
    delete HTMLElement.prototype.measureInWindow;
    expect(onMore).toHaveBeenCalledWith({ x: 796, y: 3, width: 44, height: 44 });
  });

  it('still opens the menu, without a rect, where the trigger cannot be measured', () => {
    const onMore = vi.fn();
    render(<ChatHeader kind="profile" title="doc" onMore={onMore} />);
    fireEvent.click(screen.getByLabelText('More'));
    expect(onMore).toHaveBeenCalledWith(null);
  });

  it('draws neither the dot nor the count while no job failed', () => {
    render(<ChatHeader kind="profile" title="doc" onMore={() => {}} />);
    expect(screen.getByLabelText('More')).toBeTruthy();
    expect(document.querySelector('[testid="failed-jobs-dot"]')).toBeNull();
  });

  it('keeps the Sessions button on its own icon, apart from the Schedule item', () => {
    const schedule = headerMenuActions({ onOpenSchedule: () => {} }).find((a) => a.id === 'schedule');
    expect(schedule.icon.props.name).toBe('clock');
    render(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} />);
    expect(screen.getByLabelText('Sessions').textContent).toBe('history');
  });
});

describe('ChatHeader button size', () => {
  const slopped = (label) => {
    const el = screen.getByLabelText(label);
    const style = styleOf(el);
    const slop = Number(el.getAttribute('data-hitslop'));
    return { style, slop };
  };

  it('draws every header control at the chrome size with 44pt of touch around it', () => {
    render(
      <ChatHeader kind="profile" title="doc" onBack={() => {}} onPickSession={() => {}} onMore={() => {}} />,
    );
    for (const label of ['Back', 'Sessions', 'More']) {
      const { style, slop } = slopped(label);
      expect(style.width).toBe(CHROME_BTN);
      expect(style.height).toBe(CHROME_BTN);
      expect(slop).toBe(tapSlop(CHROME_BTN));
      expect(style.height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
    }
  });

  it('keeps the two-pane controls on the very same box', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} onMore={() => {}} />);
    for (const label of ['Sessions', 'More']) {
      const { style, slop } = slopped(label);
      expect(style.height).toBe(CHROME_BTN);
      expect(style.height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
    }
  });
});

describe('ChatHeader meta row', () => {
  const meta = (
    <>
      <span data-meta="model">deepseek-v4-flash-0731</span>
      <span data-meta="context">20K/200K</span>
      <span data-meta="cost">$0.50/$2.00</span>
    </>
  );

  function scroller() {
    return document.querySelector('[data-scroll]');
  }

  it('scrolls the meters horizontally with no visible indicator', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" meta={meta} />);
    expect(scroller().getAttribute('data-scroll')).toBe('horizontal');
    expect(scroller().getAttribute('data-indicator')).toBe('false');
    expect(scroller().querySelectorAll('[data-meta]').length).toBe(3);
  });

  it('locks the pan to one axis so the transcript keeps its vertical scroll', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" meta={meta} />);
    expect(scroller().getAttribute('data-locked')).toBe('true');
  });

  it('neither stretches nor centres when the meters are narrower than the pane', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" meta={meta} />);
    const outer = JSON.parse(scroller().getAttribute('data-style'));
    const content = JSON.parse(scroller().getAttribute('data-content-style'));
    expect(outer.flexGrow).toBe(0);
    expect(content.flexGrow).toBeUndefined();
    expect(content.justifyContent).toBeUndefined();
    expect(content.flexDirection).toBe('row');
    expect(content.gap).toBe(space.s6);
  });

  it('rules between the meters on two panes only, like the desktop meta row', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" meta={meta} />);
    expect(scroller().querySelectorAll('[data-meta]').length).toBe(3);
    expect(scroller().querySelectorAll('[testid="meta-sep"]').length).toBe(2);
    cleanup();
    render(<ChatHeader kind="profile" title="doc" meta={meta} />);
    expect(scroller()).toBeNull();
    expect(document.querySelectorAll('[testid="meta-sep"]').length).toBe(0);
  });

  it('leaves a plain string meta unscrolled', () => {
    render(<ChatHeader kind="profile" title="doc" meta="profile · not found" />);
    expect(scroller()).toBeNull();
    expect(screen.getByText('profile · not found')).toBeTruthy();
  });

  it('keeps Sessions and the menu on the phone, beside a meta row that does not scroll', () => {
    const onPickSession = vi.fn();
    const onMore = vi.fn();
    render(
      <ChatHeader kind="profile" title="doc" meta={meta} onPickSession={onPickSession} onMore={onMore} />,
    );
    expect(scroller()).toBeNull();
    screen.getByLabelText('Sessions').click();
    screen.getByLabelText('More').click();
    expect(onPickSession).toHaveBeenCalledTimes(1);
    expect(onMore).toHaveBeenCalledTimes(1);
  });

  it('keeps Sessions and the menu out of the scroller under two panes', () => {
    const onPickSession = vi.fn();
    const onMore = vi.fn();
    inTwoPane(
      <ChatHeader kind="profile" title="doc" meta={meta} onPickSession={onPickSession} onMore={onMore} />,
    );
    expect(scroller().querySelector('[aria-label="Sessions"]')).toBeNull();
    expect(scroller().querySelector('[aria-label="More"]')).toBeNull();
    screen.getByLabelText('Sessions').click();
    screen.getByLabelText('More').click();
    expect(onPickSession).toHaveBeenCalledTimes(1);
    expect(onMore).toHaveBeenCalledTimes(1);
  });

  it('lets the controls keep their width while the meters take the rest', () => {
    const { container } = inTwoPane(
      <ChatHeader kind="profile" title="doc" meta={meta} onPickSession={() => {}} onMore={() => {}} />,
    );
    const actions = [...container.querySelectorAll('div')]
      .find((el) => el.querySelector('[aria-label="More"]') && styleOf(el).flexShrink === 0);
    expect(actions).toBeTruthy();
    expect(actions.querySelector('[data-scroll]')).toBeNull();
  });
});

describe('headerMenuActions failed jobs', () => {
  const schedule = (props) => headerMenuActions({ onOpenSchedule: () => {}, ...props }).find((a) => a.id === 'schedule');

  it('says how many failed in the danger tone and puts a badge on the icon', () => {
    const item = schedule({ failedJobs: 3 });
    expect(item.detail).toBe('3 failed');
    expect(item.detailDanger).toBe(true);
    expect(item.badge).toBe(true);
  });

  it('says nothing while no job failed', () => {
    const item = schedule({ failedJobs: 0 });
    expect(item.detail).toBeUndefined();
    expect(item.badge).toBeUndefined();
    expect(schedule({}).detail).toBeUndefined();
  });
});

describe('headerMenuActions', () => {
  const ALL = {
    onOpenSettings: vi.fn(),
    onTogglePause: vi.fn(),
    onToggleAutoRead: vi.fn(),
    onOpenSkills: vi.fn(),
    onOpenMemory: vi.fn(),
    onOpenTools: vi.fn(),
    onOpenSchedule: vi.fn(),
    onRefresh: vi.fn(),
  };

  it('builds the eight desktop entries in order', () => {
    expect(labels(headerMenuActions(ALL))).toEqual([
      'Profile settings',
      'Pause profile',
      'Auto-read replies',
      'Skills',
      'Memory',
      'Tools',
      'Schedule',
      'Refresh thread',
    ]);
  });

  it('carries no keyboard-shortcut hints', () => {
    const serialized = JSON.stringify(headerMenuActions(ALL).map((a) => a.label ?? ''));
    expect(serialized).not.toMatch(/⌘|⇧|Kbd|kbd/);
  });

  it('separates the brain group and the refresh tail', () => {
    const shape = headerMenuActions(ALL).map((a) => (a.divider ? '—' : a.id));
    expect(shape).toEqual([
      'settings', 'pause', 'auto-read',
      '—', 'skills', 'memory', 'tools', 'schedule',
      '—', 'refresh',
    ]);
  });

  it('offers Resume with a play glyph once paused', () => {
    const paused = headerMenuActions({ ...ALL, paused: true });
    const entry = paused.find((a) => a.id === 'pause');
    expect(entry.label).toBe('Resume profile');
    expect(entry.icon.props.name).toBe('play');
    expect(labels(paused)).toContain('Resume profile');
  });

  it('offers Pause with a pause glyph while running', () => {
    const entry = headerMenuActions(ALL).find((a) => a.id === 'pause');
    expect(entry.label).toBe('Pause profile');
    expect(entry.icon.props.name).toBe('pause');
  });

  it('offers auto-read as a switch that carries its state', () => {
    const on = headerMenuActions({ ...ALL, autoRead: true }).find((a) => a.id === 'auto-read');
    const off = headerMenuActions({ ...ALL, autoRead: false }).find((a) => a.id === 'auto-read');
    expect([on.kind, on.value, off.value]).toEqual(['switch', true, false]);
    expect(on.onValueChange).toBe(ALL.onToggleAutoRead);
  });

  it('names the workgroup noun and drops the brain group', () => {
    const actions = headerMenuActions({
      noun: 'workgroup',
      paused: true,
      onOpenSettings: ALL.onOpenSettings,
      onTogglePause: ALL.onTogglePause,
      onToggleAutoRead: ALL.onToggleAutoRead,
      onRefresh: ALL.onRefresh,
    });
    expect(labels(actions)).toEqual([
      'Workgroup settings',
      'Resume workgroup',
      'Auto-read replies',
      'Refresh thread',
    ]);
  });

  it('never opens with a divider when the head group is gone', () => {
    const actions = headerMenuActions({ onRefresh: ALL.onRefresh });
    expect(actions.map((a) => a.id)).toEqual(['refresh']);
  });

  it('wires each entry to the handler it was given', () => {
    const actions = headerMenuActions(ALL);
    for (const a of actions.filter((x) => !x.divider)) (a.onPress ?? (() => a.onValueChange(true)))();
    for (const fn of Object.values(ALL)) expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe('ChatHeader back control geometry', () => {
  it('pulls the glyph box flush to the header padding on two panes, level with the screen header back control', () => {
    h.pathname = '/wg/alpha/deep';
    render(<PaneContext.Provider value={{ twoPane: true, sidebarOpen: true, side: 'detail' }}><ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} /></PaneContext.Provider>);
    const style = styleOf(screen.getByText('back').closest('button'));
    expect(style.width).toBe(CHROME_BTN);
    expect(style.marginLeft).toBe(-(BACK_BLEED + BACK_INK_INSET));
    expect(style.marginRight).toBe(BACK_INK_INSET);
  });
});

describe('ChatHeader two-pane show-sidebar button', () => {
  it('pads 16 and bleeds the button 10 so the icon starts at x = 16, level with the screen header', () => {
    const { container } = render(
      <PaneContext.Provider value={{ twoPane: true, sidebarOpen: false, toggleSidebar() {}, side: 'detail' }}>
        <ChatHeader kind="workgroup" title="#alpha" />
      </PaneContext.Provider>,
    );
    const wrap = screen.getByLabelText('Show sidebar').parentElement;
    const margin = styleOf(wrap).marginLeft;
    expect(headerStyle(container).paddingHorizontal).toBe(PANE_PAD_X);
    expect(margin).toBe(-TOGGLE_BLEED);
    expect(headerStyle(container).paddingHorizontal + margin + (CHROME_BTN - iconSizes.md) / 2).toBe(16);
  });
});

describe('ChatHeader flag', () => {
  it('draws a passive flag beside the name on the phone and in two panes, spoken by its label', () => {
    for (const mount of [(n) => render(n), inTwoPane]) {
      const { container } = mount(<ChatHeader kind="profile" accent="#3899e2" named title="doc" flag={{ label: 'Context 85% full', tone: 'warning' }} />);
      const flag = document.querySelector('[testid="header-flag"]');
      expect(flag.getAttribute('aria-label')).toBe('Context 85% full');
      expect(styleOf(flag).backgroundColor).toBe('#e08a3c');
      expect(flag.previousElementSibling.textContent).toBe('doc');
      cleanup();
      expect(container.querySelector('[testid="header-flag"]')).toBeNull();
    }
    render(<ChatHeader kind="profile" accent="#3899e2" named title="doc" />);
    expect(document.querySelector('[testid="header-flag"]')).toBeNull();
  });
});
