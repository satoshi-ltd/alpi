import { mixHex } from '../../../common/color.mjs';
import { bannerTint } from '../../../common/tokens.mjs';

export const BANNER_TINT = bannerTint;

const HUE = { danger: 'danger', warning: 'warning', success: 'success', info: 'ink' };
const TEXT = { danger: 'dangerText', warning: 'warningText', success: 'successText', info: 'ink2' };
export const LEAD_DOT = { info: 'ink3', success: 'successText' };

export function bannerTones(kind, colors, mode) {
  const tone = HUE[kind] ? kind : 'info';
  const amounts = BANNER_TINT[mode] ?? BANNER_TINT.light;
  return {
    tone,
    surface: mixHex(colors[HUE[tone]], tone === 'info' ? amounts.quiet : amounts.tint, colors.bg),
    text: colors[TEXT[tone]],
    lead: LEAD_DOT[tone] ? colors[LEAD_DOT[tone]] : colors[TEXT[tone]],
  };
}
