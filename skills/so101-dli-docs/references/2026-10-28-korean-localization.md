# Korean localization — AI Days Seoul 2026

Source: `AI-days-seoul` / `f04378a34f4366749481f3ccf50abaa85d419501`.
User preference confirmed in AIDaySeoul2026-DLI on 2026-10-28.

- Explain concepts and procedures in natural Korean. Retain Physical AI,
  Sim-to-Real, Vision-Language-Action (VLA), Co-Training, HG-DAgger, SO-101,
  LeRobot, GR00T, Isaac Lab, Domain Randomization and other established technical
  terms and proper nouns in English.
- Keep terminology visible in English slide captures, figures and diagrams.
  Preserve original slide pixels and diagram item names. Translate interactive
  explanations, help, accessibility announcements and dynamically updated prose
  into Korean. Numeric values, equations and technical control labels stay intact.
  The user's 2026-10-28 correction supersedes the earlier interpretation that
  whole interactive diagrams and training widgets should remain English.
- Preserve shaded inline-code words, CLI flags, commands, paths, identifiers,
  literal task instructions and code blocks verbatim. Translate the surrounding
  prose, explanations, table cells and procedure labels. Bold prose can be
  translated; technical terms within it stay English.
- Do not change measurements, units, sample sizes, benchmark conditions or
  safety semantics. Historical results describe the source tag, not a new test.
  This request does not authorize model training or robot movement.

The English Markdown remains the source. Korean catalogs are in
`docs/locale/ko/LC_MESSAGES/*.po`. Sphinx uses the same Markdown, code, media,
page paths and original anchors for both languages. `docs/_ext/course_i18n.py`
repairs missing MyST 4 table-cell source metadata before Sphinx's Locale
transform, restores original heading-slug metadata after Locale reparses translated fragments, and supplies the language link. Generated `.mo` files are ignored.

Raw HTML and copied iframe/JavaScript assets bypass Sphinx gettext. Their
explanations are maintained in `docs/locale/ko/interactive.json` and applied by
`docs/_ext/interactive_i18n.py` only to Korean output. Source fragments are
file-scoped and matched exactly; stale entries fail the build. Code, links and
control IDs are checked for preservation. Catalog changes invalidate cached
Korean doctrees, including when only the translation changes. English assets
remain unchanged.

```bash
bash skills/so101-dli-docs/scripts/build.sh all all  # all six language/audience builds
bash skills/so101-dli-docs/scripts/build.sh event ko
```

Outputs: `docs/_build/{learner,event,instructor}/html` and
`docs/_build/ko/{learner,event,instructor}/html`. A language link retains the current page.
The preview already serves this whole build root; no new port/process is needed.

When English changes:

1. Build all three English audiences with `build.sh all en`.
2. Run `.venv/bin/python skills/so101-dli-docs/scripts/localization.py extract`.
   It unions the three built English doctrees into `.local/i18n/messages/*.pot`,
   including event-only paragraphs and MyST table cells. It does not overwrite
   translations. Read only these trusted, locally built pickle artifacts.
3. Merge/review the affected `.po` entries. Translate new prose; retain technical
   labels deliberately. Remove stale source entries and any fuzzy flags only
   after review. Avoid whole-file auto-translation of executable text.
   For interactive files, also review every hidden definition, help paragraph,
   raw include and JavaScript-generated status against `interactive.json`.
4. Run `localization.py check` and build both languages with warnings as errors.
   The check compares inline-code values and Markdown link destinations.
5. Run `.venv/bin/python skills/so101-dli-docs/scripts/verify_html.py --profile all`. Compare rendered code blocks between languages, local links and anchors,
   original heading anchors, language switches and audience differences. Check
   Korean navigation, images, lazy iframe loading and video playback in a browser.
   Click every interactive hotspot, use keyboard selection and reset, and change
   batch/horizon/image-comparison controls. Verify the resulting descriptions
   remain Korean after interaction, not merely at first load. Inspect the parent
   iframe height after selection so long translations are not clipped.

For the full interaction check, use Node.js 22+ and Google Chrome:

```bash
node skills/so101-dli-docs/scripts/verify_interactive.mjs http://127.0.0.1:8095 --profile all
```

It starts and cleans up its own headless Chrome profile. Evidence is saved in
`.local/docs-interactive-browser.json`. The 2026-10-28 run passed 20 diagrams,
108 selections in each of four language/audience combinations (432 selections),
GR00T calculations/reset, image comparison modes/opacity/reset, keyboard
selection/Escape, and iframe resizing. The 390px check confirms the translated
explanation fits. The whole GR00T page retains pre-existing table/theme overflow
in both English and Korean (704px scroll width); this is not a mobile-page layout
qualification. Four strict builds and the existing link/code checks also pass.

A successful build does not establish robot or policy performance. Record the
actual source revision, build and browser evidence separately.

Two stale upstream interactive links were repaired: training-stage demonstration coverage now points to `10-groot.html#overfitting`; Cosmos source-video guidance points to `14-strategy3-cosmos.html#discussion-assess-video-augmentation`.
