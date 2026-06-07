// Pure block segmentation for RichText — import-free so it stays unit-testable.

export function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
}

export function segmentBlocks(text) {
  const lines = (text ?? '').split('\n');
  const blocks = [];
  let listBuf = null;
  const flush = () => {
    if (listBuf) {
      blocks.push({ type: 'list', items: listBuf });
      listBuf = null;
    }
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trimEnd();

    const fence = /^```(.*)$/.exec(line.trim());
    if (fence) {
      flush();
      const lang = fence[1].trim().split(/\s+/)[0];
      const code = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence
      blocks.push({ type: 'code', lang, code: code.join('\n') });
      continue;
    }

    if (
      /^\|.*\|$/.test(line.trim()) &&
      i + 1 < lines.length &&
      /^\|[\s:|-]+\|$/.test(lines[i + 1].trim())
    ) {
      flush();
      const header = splitRow(line);
      i += 2; // header + separator
      const rows = [];
      while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
        rows.push(splitRow(lines[i]));
        i += 1;
      }
      blocks.push({ type: 'table', header, rows });
      continue;
    }

    if (!line.trim()) {
      flush();
      blocks.push({ type: 'space' });
      i += 1;
      continue;
    }

    // Standalone agent image: ![alt](/abs/path.png "note"). Local absolute paths only.
    const img = /^!\[([^\]]*)\]\((\/[^\s)]+\.(?:png|jpe?g|webp|gif))(?:\s+"([^"]*)")?\)$/i.exec(
      line.trim(),
    );
    if (img) {
      flush();
      blocks.push({ type: 'image', path: img[2], alt: img[1], note: img[3] || '' });
      i += 1;
      continue;
    }

    const h = /^#{1,3} (.+)$/.exec(line);
    if (h) {
      flush();
      blocks.push({ type: 'heading', text: h[1] });
      i += 1;
      continue;
    }

    const li = /^[-*] (.+)$/.exec(line);
    if (li) {
      if (!listBuf) listBuf = [];
      listBuf.push(li[1]);
      i += 1;
      continue;
    }

    flush();
    blocks.push({ type: 'p', text: line });
    i += 1;
  }
  flush();
  return blocks;
}
