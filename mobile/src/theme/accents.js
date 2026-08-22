
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
