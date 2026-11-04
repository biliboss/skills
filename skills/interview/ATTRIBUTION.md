# Attribution

The form itself (the questions UI, the form server and the schema in `vendor/package/`) is the `pi-interview` package, vendored here with a few local patches for the queue (marked `Local patch` in `server.ts` and `form/script.js`).

| Package | Version | Author | License | Source |
|---|---|---|---|---|
| [pi-interview](https://github.com/nicobailon/pi-interview-tool) | 0.14.0 | Nico Bailon | MIT | https://github.com/nicobailon/pi-interview-tool |

The package declares `"license": "MIT"` and `"author": "Nico Bailon"` in its `package.json` and ships no separate LICENSE file, so the standard MIT text is reproduced below for the author named there.

## License text (MIT)

> Copyright (c) Nico Bailon
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## What is ours

`interview.ts` (the client), `queue.ts` (the queue server), `launch.ts`, `config.ts` and `test/` are original to this skill.

To check for upstream changes: compare the version above with `npm view pi-interview version`.
