# AI Hub Web UI Notes

The browser UI has been restored to the retro "OG" layout that shipped with Project Frank before these recent iterations. Key expectations moving forward:

- **Visual style**: keep the neon CRT-inspired palette (deep navy background, cyan/yellow accents, blocky Courier text). No modern gradients, cards, or rounded layouts.
- **Structure**: preserve the left-hand menu with MAIN MENU / CHAT / MODELS / SETTINGS / LOGS and the matching hub panes. Menu text should stay uppercase with minimal ornamentation.
- **ASCII hygiene**: the old glyphs like `dY'` were artifacts from a bad code page. All text should now be plain ASCII equivalents so the UI renders cleanly on any machine.
- **Feature parity**: the restored HTML still supports model selection, Gemini quick-pick, settings, and logs exactly as before. Any future changes should start from this layout and call out modifications explicitly.

Claude: please reference this document if further tweaks are needed. The current deliverable is simply the original UI look (sans corrupted characters) with the existing functionality intact.
