
export const profileAccents = {
  alpi: '#b8954a',
  doc: '#3d7ea6',
  builder: '#c14545',
  vera: '#9d4dc6',
  abby: '#c14580',
  etxea: '#2f7d6e',
  ghost: '#6c7480',
  archive: '#8a7a4a',
  atlas: '#3d7ea6',
  canvas: '#9d4dc6',
  echo: '#d97757',
  fern: '#3fb37a',
  flux: '#6a6dd6',
  forge: '#2f7d6e',
  hub: '#3d7ea6',
  ledger: '#3fb37a',
  lex: '#6c7480',
  lumen: '#2f8e9e',
  prism: '#3fb37a',
  quill: '#8a7a4a',
  rex: '#d97757',
  sentinel: '#c14580',
  zeta: '#6a6dd6',
};

export const accentForProfile = (id, fallback = '#7c8896') =>
  profileAccents[id === 'default' ? 'alpi' : id] ?? fallback;

// Picker palette — same hexes as profileAccents but with human-readable names
// for the accent picker UI (Settings · Accent). Ordered by hue family.
export const namedAccents = [
  ['gold', '#b8954a'],
  ['terracotta', '#d97757'],
  ['brick', '#c14545'],
  ['magenta', '#c14580'],
  ['purple', '#9d4dc6'],
  ['indigo', '#6a6dd6'],
  ['denim', '#3d7ea6'],
  ['teal', '#2f8e9e'],
  ['pine', '#2f7d6e'],
  ['forest', '#3fb37a'],
  ['olive', '#8a7a4a'],
  ['slate', '#6c7480'],
];
