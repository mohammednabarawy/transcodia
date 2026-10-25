# Asset creation record

Transcodia's app mark, README banner and 23 interface icons were generated for this project with ChatGPT's built-in `image_gen` tool on 2026-10-26. The interface icons are individual transparent PNG files, not code-drawn replacements or external application resources.

## Files

- `transcodia_app/assets/app-mark.png` — abstract cobalt/turquoise ribbon T mark.
- `transcodia_app/assets/icons/` — 23 generated action/category icons, loaded by `transcodia_app/icons.py`.
- `packaging/transcodia.ico` and `packaging/transcodia.icns` — platform encodings derived from the generated app mark.
- `_docs/images/brand-banner.png` — generated README banner using the project mark as its only image reference.
- `_docs/images/main-window*.png`, `pdf-joiner.png` and `ui-icons.png` — captures of actual project widgets, produced by `scripts/render_screenshots.py`.

The app asset manifest records file hashes, dimensions and the interface prompt set. Each toolbar/tool image uses the same style brief with its own subject: video, audio, picture, document, disc, utilities, folder, options, remove, clear, stop, start, pause, home, add files, confirm, join, split, clip, delogo, frames, recorder and download. Format tiles reuse the relevant category image and retain their own text label.

## Brand prompt

An original desktop application emblem for Transcodia: an abstract T made from interlocking rounded cobalt and turquoise ribbons, with a restrained indigo accent, a strong small-size silhouette and a transparent background. No other logos, words or watermark.

## Interface prompt set

The full prompts are stored in `transcodia_app/assets/manifest.json`. Each requests one transparent PNG icon with crisp rounded strokes, cobalt/turquoise colors, restrained pale cyan fill, readable geometry at 24–32 pixels and no lettering, background tile, drop shadow or existing application logo. The subject changes for each action listed above.

## Banner prompt

A wide, near-white Transcodia README banner using the generated T emblem as the brand reference. Restrained cobalt/turquoise/indigo identity, subtle pale gradients, generous margins and the exact text “Transcodia” and “Media and documents, in your format.” Small original file motifs suggest video, audio, image and document workflows. No fabricated product screenshot or other brand marks.

These are creation records and technical checks. They do not establish exclusive copyright eligibility, global visual uniqueness or independent trademark clearance. Dependency artwork and font notices, where applicable, remain governed by their upstream licenses.
