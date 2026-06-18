export function pickEffectiveModel(modelOverride, sessionModel, profileModel) {
  return modelOverride ?? sessionModel ?? profileModel;
}
