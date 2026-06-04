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

  it("rejects unsupported types (zip, office, heic) and code outside the minimal set", () => {
    for (const name of ["bundle.zip", "doc.docx", "sheet.xlsx", "pic.heic", "deck.pages", "noext", "a.rb", "b.java", "c.cpp"]) {
      expect(attachmentMimeFor(name)).toBe("");
      expect(isSupportedAttachment(name)).toBe(false);
    }
  });

  it("isSupportedAttachment is true for allowlisted names", () => {
    expect(isSupportedAttachment("a.png")).toBe(true);
    expect(isSupportedAttachment("a.csv")).toBe(true);
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
