// Zero-dependency Markdown → HTML renderer.
// Intentionally minimal: handles the subset used by alpi docs.
// Supported: ATX headings, fenced code blocks, paragraphs, bullet + ordered
// lists (one level), blockquotes, horizontal rules, GFM-style pipe tables,
// inline code, bold, italic, links, raw HTML blocks (passed through).

const HTML_BLOCK_TAGS = /^<(div|section|article|aside|header|footer|nav|table|ul|ol|p|pre|blockquote|details|summary|figure|figcaption|hr|br|iframe)\b/i;

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escAttr(s) {
  return esc(s).replace(/"/g, '&quot;');
}

function slug(s) {
  return s.toLowerCase()
    .replace(/<[^>]+>/g, '')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 80);
}

function renderInline(src, linkRewrite) {
  let out = '';
  let i = 0;
  const n = src.length;
  while (i < n) {
    const c = src[i];

    // Escaped char
    if (c === '\\' && i + 1 < n) {
      out += esc(src[i + 1]);
      i += 2;
      continue;
    }

    // Inline code `...`
    if (c === '`') {
      const end = src.indexOf('`', i + 1);
      if (end !== -1) {
        out += '<code>' + esc(src.slice(i + 1, end)) + '</code>';
        i = end + 1;
        continue;
      }
    }

    // Link [text](url)
    if (c === '[') {
      const close = src.indexOf(']', i + 1);
      if (close !== -1 && src[close + 1] === '(') {
        const paren = src.indexOf(')', close + 2);
        if (paren !== -1) {
          const text = src.slice(i + 1, close);
          let url = src.slice(close + 2, paren).trim();
          let title = '';
          const tMatch = url.match(/^(\S+)\s+"([^"]*)"$/);
          if (tMatch) { url = tMatch[1]; title = tMatch[2]; }
          if (linkRewrite) url = linkRewrite(url);
          out += `<a href="${escAttr(url)}"${title ? ` title="${escAttr(title)}"` : ''}>${renderInline(text, linkRewrite)}</a>`;
          i = paren + 1;
          continue;
        }
      }
    }

    // Bold **...**
    if (c === '*' && src[i + 1] === '*') {
      const end = src.indexOf('**', i + 2);
      if (end !== -1) {
        out += '<strong>' + renderInline(src.slice(i + 2, end), linkRewrite) + '</strong>';
        i = end + 2;
        continue;
      }
    }

    // Italic *...* (single)
    if (c === '*') {
      const end = src.indexOf('*', i + 1);
      if (end !== -1 && end !== i + 1) {
        out += '<em>' + renderInline(src.slice(i + 1, end), linkRewrite) + '</em>';
        i = end + 1;
        continue;
      }
    }

    // Autolink bare URL (very loose)
    if (c === 'h' && src.startsWith('http', i)) {
      const m = src.slice(i).match(/^https?:\/\/[^\s<>)\]]+/);
      if (m) {
        const url = m[0];
        out += `<a href="${escAttr(url)}">${esc(url)}</a>`;
        i += url.length;
        continue;
      }
    }

    out += esc(c);
    i += 1;
  }
  return out;
}

function renderTable(rows, linkRewrite) {
  const head = rows[0];
  const body = rows.slice(2);
  const th = head.map(c => `<th>${renderInline(c.trim(), linkRewrite)}</th>`).join('');
  const rowsHtml = body.map(r =>
    '<tr>' + r.map(c => `<td>${renderInline(c.trim(), linkRewrite)}</td>`).join('') + '</tr>'
  ).join('\n');
  return `<table>\n<thead><tr>${th}</tr></thead>\n<tbody>\n${rowsHtml}\n</tbody>\n</table>`;
}

function splitRow(line) {
  const s = line.replace(/^\s*\|/, '').replace(/\|\s*$/, '');
  return s.split('|');
}

export function renderMarkdown(src, opts = {}) {
  const linkRewrite = opts.linkRewrite || null;
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Blank line
    if (/^\s*$/.test(line)) { i += 1; continue; }

    // Fenced code block ``` or ~~~
    const fence = line.match(/^(\s*)(```+|~~~+)\s*([^\s`]*)\s*$/);
    if (fence) {
      const marker = fence[2];
      const lang = fence[3] || '';
      const buf = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith(marker.slice(0, 3))) {
        buf.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) i += 1;
      const classAttr = lang ? ` class="language-${escAttr(lang)}"` : '';
      out.push(`<pre><code${classAttr}>${esc(buf.join('\n'))}</code></pre>`);
      continue;
    }

    // ATX heading
    const heading = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2];
      const id = slug(text);
      out.push(`<h${level} id="${escAttr(id)}">${renderInline(text, linkRewrite)}</h${level}>`);
      i += 1;
      continue;
    }

    // Horizontal rule
    if (/^\s*(\*\s*){3,}$|^\s*(-\s*){3,}$|^\s*(_\s*){3,}$/.test(line)) {
      out.push('<hr />');
      i += 1;
      continue;
    }

    // Blockquote
    if (/^\s*>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        buf.push(lines[i].replace(/^\s*>\s?/, ''));
        i += 1;
      }
      out.push('<blockquote>\n' + renderMarkdown(buf.join('\n'), opts) + '\n</blockquote>');
      continue;
    }

    // Table (pipe row followed by separator row)
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i + 1])) {
      const rows = [splitRow(line), splitRow(lines[i + 1])];
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows.push(splitRow(lines[i]));
        i += 1;
      }
      out.push(renderTable(rows, linkRewrite));
      continue;
    }

    // Unordered list
    const ulm = line.match(/^(\s*)[-*+]\s+(.*)$/);
    if (ulm) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)[-*+]\s+(.*)$/);
        if (m) {
          const buf = [m[2]];
          i += 1;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^(\s*)[-*+]\s+/.test(lines[i])) {
            buf.push(lines[i].replace(/^\s{2}/, ''));
            i += 1;
          }
          items.push(buf.join('\n'));
        } else if (/^\s*$/.test(lines[i]) && i + 1 < lines.length && /^(\s*)[-*+]\s+/.test(lines[i + 1])) {
          i += 1;
        } else {
          break;
        }
      }
      const li = items.map(t => `<li>${renderInline(t.trim(), linkRewrite)}</li>`).join('\n');
      out.push(`<ul>\n${li}\n</ul>`);
      continue;
    }

    // Ordered list
    const olm = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (olm) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)\d+\.\s+(.*)$/);
        if (m) {
          const buf = [m[2]];
          i += 1;
          while (i < lines.length && /^\s{3,}\S/.test(lines[i]) && !/^(\s*)\d+\.\s+/.test(lines[i])) {
            buf.push(lines[i].replace(/^\s{3}/, ''));
            i += 1;
          }
          items.push(buf.join('\n'));
        } else if (/^\s*$/.test(lines[i]) && i + 1 < lines.length && /^(\s*)\d+\.\s+/.test(lines[i + 1])) {
          i += 1;
        } else {
          break;
        }
      }
      const li = items.map(t => `<li>${renderInline(t.trim(), linkRewrite)}</li>`).join('\n');
      out.push(`<ol>\n${li}\n</ol>`);
      continue;
    }

    // Raw HTML block — pass through until blank line
    if (HTML_BLOCK_TAGS.test(line)) {
      const buf = [line];
      i += 1;
      while (i < lines.length && !/^\s*$/.test(lines[i])) {
        buf.push(lines[i]);
        i += 1;
      }
      out.push(buf.join('\n'));
      continue;
    }

    // Paragraph
    const buf = [line];
    i += 1;
    while (i < lines.length && !/^\s*$/.test(lines[i])
           && !/^#{1,6}\s/.test(lines[i])
           && !/^```/.test(lines[i])
           && !/^\s*[-*+]\s+/.test(lines[i])
           && !/^\s*\d+\.\s+/.test(lines[i])
           && !/^\s*>/.test(lines[i])) {
      buf.push(lines[i]);
      i += 1;
    }
    out.push(`<p>${renderInline(buf.join(' '), linkRewrite)}</p>`);
  }

  return out.join('\n\n');
}
