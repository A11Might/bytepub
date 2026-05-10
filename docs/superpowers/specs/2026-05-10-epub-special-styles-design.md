# EPUB Special Styles Design

## Problem

ByteByteGo course pages contain several special HTML elements whose visual styles
are lost during EPUB generation. The cleaned HTML preserves the class names and
structure, but the `EPUB_CSS` in `builder.py` does not include corresponding
rules, so these elements render as plain unstyled content in the EPUB reader.

Four specific issues:

1. **info-box** — tip/note callout boxes with icon images; no border or background.
2. **sample-dialogue** — interview dialogue blocks; no visual framing.
3. **hljs code blocks** — `<pre><code class="hljs language-java">` with semantic
   highlight classes; no code-block styling or syntax colors.
4. **✅ emoji** — not renderable on some EPUB readers (especially Kindle).

## Approach

Structural HTML transforms in `cleaner.py`, visual styles in `builder.py` CSS.

## Changes

### cleaner.py — `_process_styles(content: Tag)`

New function called from `clean_page()` after existing processing steps.

**Emoji replacement:**

- Walk all `NavigableString` nodes in the content tree.
- Replace `✅` with `[√]`.

info-box, sample-dialogue, and hljs code blocks need no structural changes; the
HTML already has the right elements and classes.

### builder.py — `EPUB_CSS` extension

Append the following rules to the existing `EPUB_CSS` constant:

```css
/* info-box */
.info-box {
    border-left: 4px solid #4a90d9;
    background-color: #f0f4f8;
    padding: 0.8em 1em;
    margin: 1em 0;
    display: flex;
    align-items: flex-start;
    gap: 0.5em;
}
.info-box img {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
}

/* sample-dialogue */
.sample-dialogue {
    border: 1px solid #bbb;
    background-color: #f5f5f5;
    padding: 0.8em 1em;
    margin: 1em 0;
}
.sample-dialogue p {
    margin: 0.3em 0;
}

/* code blocks */
pre {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    padding: 0.8em 1em;
    margin: 1em 0;
    overflow-x: auto;
    font-family: monospace;
    font-size: 0.9em;
    line-height: 1.4;
    white-space: pre;
}
code {
    font-family: monospace;
    font-size: 0.9em;
}
pre code {
    background: none;
    border: none;
    padding: 0;
}

/* hljs syntax highlighting — grayscale-safe colors */
.hljs-keyword,
.hljs-built_in {
    font-weight: bold;
    color: #1a3a6b;
}
.hljs-comment {
    color: #888;
    font-style: italic;
}
.hljs-string {
    color: #2a6a2a;
}
.hljs-type {
    color: #5a2a7a;
}
.hljs-title {
    color: #6b4a1a;
}
.hljs-meta {
    color: #888;
}
.hljs-params {
    color: inherit;
}
```

Color rationale: all chosen colors are dark enough to be distinguishable on
grayscale e-ink displays while remaining distinct from each other on color
screens.

## Files Changed

| File | Change |
|------|--------|
| `src/cleaner.py` | Add `_process_styles()`, call from `clean_page()` |
| `src/builder.py` | Extend `EPUB_CSS` constant |

## Out of Scope

- Full hljs theme with dozens of language-specific token types.
- Stripping existing hljs classes in favor of plain code (keep semantic info).
- Changing the EPUB XHTML template structure.
