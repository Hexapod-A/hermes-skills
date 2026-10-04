// Tiny logic-less template engine (mustache subset) so layouts stay plain HTML.
//   {{key}}      escaped value (dot paths ok, "." = current item)
//   {{{key}}}    raw HTML
//   {{~key}}     rich text: escaped, *word* -> accent span, "\n" -> line break
//   {{#key}}..{{/key}}  section: loops arrays, renders once for truthy values
//   {{^key}}..{{/key}}  inverted section
//   {{>name}}    partial from templates/partials/name.html
import fs from 'node:fs';
import path from 'node:path';

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const rich = (s) => esc(s).replace(/\*([^*]+)\*/g, '<span class="hl">$1</span>').replace(/\\n|\n/g, '<br>');

function lookup(stack, key) {
  if (key === '.') return stack[stack.length - 1];
  const parts = key.split('.');
  for (let i = stack.length - 1; i >= 0; i--) {
    const ctx = stack[i];
    if (ctx && typeof ctx === 'object' && parts[0] in ctx) {
      let v = ctx;
      for (const p of parts) v = v == null ? undefined : v[p];
      return v;
    }
  }
  return undefined;
}

function findClose(tpl, from, key) {
  // find matching {{/key}} accounting for nesting of the same key
  const open = new RegExp(`{{[#^]${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}}}`, 'g');
  const close = `{{/${key}}}`;
  let depth = 1, i = from;
  while (true) {
    const c = tpl.indexOf(close, i);
    if (c < 0) throw new Error(`Unclosed section {{#${key}}}`);
    open.lastIndex = i;
    let m, opens = 0;
    while ((m = open.exec(tpl)) && m.index < c) opens++;
    depth += opens - 1;
    if (depth === 0) return c;
    i = c + close.length;
  }
}

export function render(tpl, data, partialsDir, stack = [data]) {
  let out = '', i = 0;
  const re = /{{(\{|[#^>~/])?\s*([^}\s]+)\s*\}?}}/g;
  while (true) {
    re.lastIndex = i;
    const m = re.exec(tpl);
    if (!m) { out += tpl.slice(i); break; }
    out += tpl.slice(i, m.index);
    const [whole, sigil, key] = m;
    i = m.index + whole.length;
    if (sigil === '#' || sigil === '^') {
      const end = findClose(tpl, i, key);
      const inner = tpl.slice(i, end);
      i = end + `{{/${key}}}`.length;
      const v = lookup(stack, key);
      const truthy = Array.isArray(v) ? v.length > 0 : !!v;
      if (sigil === '^') { if (!truthy) out += render(inner, data, partialsDir, stack); continue; }
      if (!truthy) continue;
      if (Array.isArray(v)) for (const item of v) out += render(inner, data, partialsDir, [...stack, item]);
      else out += render(inner, data, partialsDir, typeof v === 'object' ? [...stack, v] : stack);
    } else if (sigil === '>') {
      const p = path.join(partialsDir, `${key}.html`);
      out += render(fs.readFileSync(p, 'utf8'), data, partialsDir, stack);
    } else if (sigil === '{') out += String(lookup(stack, key) ?? '');
    else if (sigil === '~') out += rich(lookup(stack, key));
    else out += esc(lookup(stack, key));
  }
  return out;
}
