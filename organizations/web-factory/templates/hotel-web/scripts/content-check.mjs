import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const pagesDir = join(process.cwd(), "src", "content", "pages");
const problems = [];

if (!existsSync(pagesDir)) {
  problems.push("missing src/content/pages");
} else {
  const files = readdirSync(pagesDir).filter((name) => name.endsWith(".json"));
  if (!files.length) problems.push("no page JSON found under src/content/pages");
  for (const name of files) {
    const path = join(pagesDir, name);
    let page;
    try {
      page = JSON.parse(readFileSync(path, "utf8"));
    } catch (error) {
      problems.push(`${name}: invalid JSON (${error.message})`);
      continue;
    }
    if (
      Object.hasOwn(page, "intro")
      && (page.intro === null || typeof page.intro !== "object" || Array.isArray(page.intro))
    ) {
      problems.push(`${name}: intro must be an object with optional title/body, never a string`);
    }
  }
}

if (problems.length) {
  console.error("content-check FAIL:");
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}

console.log("content-check OK");
