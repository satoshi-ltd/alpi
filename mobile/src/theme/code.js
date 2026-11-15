import { monoScale, typeFloor } from './tokens';

export const codeSize = (size) => Math.max(typeFloor, Math.round(size * monoScale));

export function code(fonts, size, weight = 'regular') {
  const family = weight === 'medium' ? fonts.monoMedium : weight === 'semibold' ? fonts.monoSemibold : fonts.mono;
  return { fontFamily: family, fontSize: codeSize(size) };
}
