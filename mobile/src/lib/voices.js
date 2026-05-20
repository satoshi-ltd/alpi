export const VOICE_SHORTLIST = [
  { id: 'en-US-AriaNeural', name: 'Aria', desc: 'English (US) · female' },
  { id: 'en-US-GuyNeural', name: 'Guy', desc: 'English (US) · male' },
  { id: 'en-US-JennyNeural', name: 'Jenny', desc: 'English (US) · female' },
  { id: 'en-GB-SoniaNeural', name: 'Sonia', desc: 'English (UK) · female' },
  { id: 'en-GB-RyanNeural', name: 'Ryan', desc: 'English (UK) · male' },
  { id: 'en-AU-NatashaNeural', name: 'Natasha', desc: 'English (AU) · female' },
  { id: 'en-AU-WilliamNeural', name: 'William', desc: 'English (AU) · male' },
  { id: 'es-ES-ElviraNeural', name: 'Elvira', desc: 'Spanish (ES) · female' },
  { id: 'es-ES-AlvaroNeural', name: 'Alvaro', desc: 'Spanish (ES) · male' },
  { id: 'es-MX-DaliaNeural', name: 'Dalia', desc: 'Spanish (MX) · female' },
  { id: 'fr-FR-DeniseNeural', name: 'Denise', desc: 'French · female' },
  { id: 'fr-FR-HenriNeural', name: 'Henri', desc: 'French · male' },
  { id: 'de-DE-KatjaNeural', name: 'Katja', desc: 'German · female' },
  { id: 'it-IT-ElsaNeural', name: 'Elsa', desc: 'Italian · female' },
  { id: 'pt-BR-FranciscaNeural', name: 'Francisca', desc: 'Portuguese (BR) · female' },
];

export function voiceLabel(id) {
  if (!id) return null;
  const v = VOICE_SHORTLIST.find((x) => x.id === id);
  return v ? `${v.name} · ${v.desc}` : id;
}
