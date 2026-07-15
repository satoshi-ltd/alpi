import { describe, it, expect } from "vitest";

import {
  attachmentMimeFor,
  isSupportedAttachment,
  fileKind,
} from "./fileKind.js";

describe("attachmentMimeFor / isSupportedAttachment", () => {
  it("maps the allowlisted extensions", () => {
    expect(attachmentMimeFor("shot.png")).toBe("image/png");
    expect(attachmentMimeFor("a.JPG")).toBe("image/jpeg");
    expect(attachmentMimeFor("doc.pdf")).toBe("application/pdf");
    expect(attachmentMimeFor("notes.md")).toBe("text/markdown");
    expect(attachmentMimeFor("cfg.yaml")).toBe("application/yaml");
  });

  it("accepts the supported code extensions as text/plain", () => {
    for (const name of ["main.py", "app.tsx", "x.js", "y.ts", "svc.go", "lib.rs", "run.sh", "q.sql"]) {
      expect(attachmentMimeFor(name)).toBe("text/plain");
      expect(isSupportedAttachment(name)).toBe(true);
    }
  });

  it("unknown types stage as opaque octet-stream files, not rejected", () => {
    for (const name of ["bundle.zip", "doc.docx", "sheet.xlsx", "pic.heic", "run.fit", "noext", "a.rb"]) {
      expect(attachmentMimeFor(name)).toBe("application/octet-stream");
      expect(isSupportedAttachment(name)).toBe(true);
    }
  });

  it("isSupportedAttachment is true for any real filename", () => {
    expect(isSupportedAttachment("a.png")).toBe(true);
    expect(isSupportedAttachment("a.csv")).toBe(true);
    expect(isSupportedAttachment("")).toBe(false);
  });
});

describe("fileKind", () => {
  it("classifies for the type icon", () => {
    expect(fileKind("a.png", "image/png")).toBe("image");
    expect(fileKind("main.py", "text/plain")).toBe("code");
    expect(fileKind("notes.md", "text/markdown")).toBe("text");
    expect(fileKind("doc.pdf", "application/pdf")).toBe("file");
  });
});
