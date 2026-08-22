export { compactProducedTool, stripProducedImageMarkdown } from "../../../common/producedAttachments.mjs";

export function imageProduced(produced) {
  return (produced || []).filter((a) => a?.kind === "image" && a?.path);
}

export function nonImageProduced(produced) {
  return (produced || []).filter((a) => a?.kind !== "image");
}
