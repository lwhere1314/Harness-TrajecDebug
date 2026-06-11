# Meta-Harness Repair Brief: break-filter-js-from-html

## Source Failure

- Harness: Harbor / Terminal-Bench 2.1 proxy task
- Source task: `break-filter-js-from-html`
- Prior agent: `claude-code`
- Prior model: `kimi-k2.6`
- Prior run: `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/jobs/tb21-break-filter-js-from-html-claude-code-k6`
- Prior reward: `0`

## Official Verifier Contract

Create `/app/out.html`. The verifier copies it to a temporary file, runs:

```bash
python /tests/filter.py <temporary-html-file>
```

and then opens the filtered file in headless Chromium. The filtered file must
trigger a JavaScript `alert()` automatically, with no user interaction.

## What Went Wrong Previously

The prior K2.6 trajectory read `/app/filter.py` but did not create
`/app/out.html`. The official verifier failed immediately with:

```text
AssertionError: File /app/out.html does not exist
```

No payload was evaluated.

## Current Kimi Code Without-Meta-Harness Failure

The first Kimi Code without-Meta-Harness probe did create `/app/out.html`. Its
payload used a meta refresh to a base64 `data:text/html` document containing a
script alert. The bundled filter preserved the meta refresh tag.

The official verifier still failed before payload evaluation while creating the
local Selenium/ChromeDriver session:

```text
selenium.common.exceptions.WebDriverException: Message: Service Unavailable
```

The traceback shows the `503` during `webdriver.Chrome(...).start_session`, not
after opening the filtered HTML. This suggests a local browser automation
environment/proxy issue, not yet an XSS-payload assertion failure.

## Filter Behavior Observed In The Task

The bundled filter parses the file with BeautifulSoup using `html.parser` and:

- removes `<script>` tags;
- removes `<frame>`, `<iframe>`, `<object>`, and `<embed>` tags;
- deletes attributes whose names start with `on`;
- serializes the remaining soup back to a string.

The next candidate should create the required `out.html` file, use an automatic
alert mechanism that survives exactly those transformations, and account for
the local ChromeDriver/Selenium verifier path if environment proxy settings are
present.
