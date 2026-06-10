# Oracle-Grounded Critical-Step Card: filter-js-from-html

## Oracle Ground Truth Signal

The oracle-level signal is not "build the most aggressive sanitizer." It is:

- make `/app/filter.py` a small in-place HTML transformer;
- remove executable constructs that are plainly JavaScript-bearing;
- preserve clean HTML after normal parser serialization;
- avoid broad raw-text rewrites that mutate benign tags, attributes, entities, or
  document structure.

So the critical step is a task-framing decision:

> Treat this as minimal harmful-substring removal with clean-document
> preservation as a binding gate, not as a full custom HTML rewriter.

## Corrective Direction

Use a standard HTML parser and keep the transformation boundary narrow:

1. Read the input HTML file from `sys.argv[1]`.
2. Parse with a normal HTML parser available in the image.
3. Remove only executable containers such as script-like or embedding tags.
4. Remove event-handler attributes whose names begin with `on`.
5. Remove explicit `javascript:` URL prefixes and escape literal `<script`
   substrings that survive as text.
6. Write the processed HTML back to the same path.

The important oracle-grounded constraint is that clean HTML should still compare
equal after the verifier's parser normalization. Do not reconstruct every tag by
hand, sort attributes, delete safe attributes, collapse entities beyond parser
normalization, or implement a broad denylist that changes ordinary forms,
semantic HTML, images, tables, links, and text-formatting elements.

## Critical Verifier Gate

The verifier has two distinct gates:

- XSS blocking: dangerous samples must no longer trigger JavaScript.
- Clean preservation: clean samples must remain equivalent after BeautifulSoup
  normalization and whitespace-insensitive comparison.

Historical failed agents passed the first gate and failed the second. Therefore
the first local check should be: "Does my sanitizer leave clean documents alone
under parser normalization?"

## Repair Boundary

Prefer a tiny parser-based implementation over:

- custom `HTMLParser` serializers that re-emit every tag;
- regular-expression pipelines over the whole file;
- removing all unknown tags or attributes;
- normalizing URLs, quotes, entities, or whitespace outside the explicit
  JavaScript-removal cases.

## Closure Check

Before finishing, run a small local smoke test:

```bash
python /app/filter.py /tmp/clean.html
python /app/filter.py /tmp/xss.html
```

For the clean file, compare the output to the parser-normalized input with
whitespace removed. For the XSS file, confirm no `script`, event-handler
attribute, or `javascript:` payload remains.
