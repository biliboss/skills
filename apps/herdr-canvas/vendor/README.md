# vendor/

`canvas.css` is the only stylesheet the Canvas pages use. It is compiled once and committed, so pages render offline with no CDN. The render (`skills/herdr-canvas/scripts/canvaslib.py`) inlines it in every `page.html`.

| Package | Version | License |
| --- | --- | --- |
| tailwindcss | 4.3.5 | MIT, https://github.com/tailwindlabs/tailwindcss |
| @tailwindcss/cli | 4.3.5 | MIT |
| daisyui | 5.7.50 | MIT, https://github.com/saadeghi/daisyui |

Themes: `light` (default) and `dark` (also when the system prefers dark). The page picks one with `data-theme` from the `?theme=` query.

Contents: Tailwind preflight, the utilities and daisyUI components listed in `classes.html`, and the page styles in `canvas.src.css` (`cv-*`). A class that is not in `classes.html` is not in the CSS; HTML blocks can only use the listed ones.

## Rebuild

Do it in a throwaway folder outside the repo; the repo has no npm dependency.

```sh
work=$(mktemp -d) && cd "$work" && npm init -y && npm i tailwindcss@4 @tailwindcss/cli@4 daisyui@5
cp <repo>/apps/herdr-canvas/vendor/canvas.src.css <repo>/apps/herdr-canvas/vendor/classes.html .
./node_modules/.bin/tailwindcss -i canvas.src.css -o canvas.css --minify
cp canvas.css <repo>/apps/herdr-canvas/vendor/canvas.css
```

Then update the versions above. The only `http://` strings in the CSS are SVG `xmlns` attributes inside `data:` URIs; nothing is fetched.
