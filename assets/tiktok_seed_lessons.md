# TikTok publisher lessons (seed)

Bootstrap lessons that travel with the repo. On a fresh server, this
file is copied to `.storage/tiktok_learnings.md`, which then accumulates
new lessons over time via the post-run reflector. Edit by hand and
push back with `just push-tiktok-learnings` if needed.

## Hard-rule reminders (echoed in every task prompt — keep them strict)

- The agent has NO vision; it only sees the DOM. Many TikTok elements
  share the same CSS class — we MUST identify by visible text or by
  unique fingerprints, never by raw index alone.
- The four left-sidebar buttons all have class `Sidebar_Sidebar_Clickable`
  and are indistinguishable to a text-only LLM. NEVER click any
  sidebar element. Stay in the right-hand main content area.
- `upload_file_to_element` is fire-and-forget. After it returns, the
  page takes 5-10 s to render the preview. NEVER call it twice for the
  same task — duplicate uploads waste 5+ steps and confuse TikTok.

## Login flow (pt-BR)

- Click the tab labeled "Usar telefone / e-mail / nome de usuário" to
  switch from QR-code to credentials login.
- Then click the inner tab "Entrar com nome de usuário ou e-mail" to
  reveal the email + password inputs.
- The submit button is labeled "Entrar".
- Sometimes TikTok redirects to "/" or "/foryou" instead of
  /tiktokstudio after a successful login. Re-navigate to
  /tiktokstudio/upload?from=upload ONCE in that case (don't keep going
  back).

## Captcha handling

- Slider captcha pt-BR text: "Arraste o controle deslizante para
  encaixar o quebra-cabeças".
- DO NOT try to solve sliders — wait 30 s, recheck URL, repeat up to 4
  times. A human is watching the VNC window during bootstrap and will
  drag it.
- After the human solves it, the URL contains `/tiktokstudio` or
  `/foryou` — proceed to the upload steps.

## Studio upload page

- Canonical URL: `https://www.tiktok.com/tiktokstudio/upload?from=upload`
- The UPLOAD DROP ZONE is a `<div role="button">` (not an `<input>`)
  containing visible text such as "Selecionar vídeo", "Select video",
  or "Drag and drop". Use `upload_file_to_element` with its index.
- After upload, wait for a "Cover" / "Editar capa" panel or a `<video>`
  element. Do NOT keep retrying the upload — it's already in flight.
- The CAPTION editor is a `<div contenteditable="true">` near the top
  of the right-hand form. NOT a `<textarea>`. Placeholder text reads
  "Descreva seu vídeo..." or similar.
- IMPORTANT: TikTok auto-prefills the caption with the uploaded file's
  basename (e.g. uploading `part1.mp4` puts "part1" in the field). You
  MUST clear the field (Ctrl+A + Delete) before typing the description,
  or the result will be `<filename><description>` concatenated.

## Onboarding & ghost popups

- "Preview your video on phone" / "Pronto" overlay: one pink "Got it"
  button. Click it, move on. One-time per device.
- A "Smart Split" sibling tab may appear suggesting to split long
  videos. IGNORE it; stay on the original "TikTok Studio" tab.
- A native OS file-picker dialog occasionally lingers after upload.
  Press Escape to close it; do NOT click "Cancel" inside the dialog.
- "Discard this post?" confirmation: click the SECONDARY button
  (Cancel / Manter rascunho), NEVER the primary red "Discard" — that
  wipes the upload progress.

## Scheduling (pt-BR)

- The schedule toggle lives in a section labeled "Quando postar"
  (or "When to post"). Two radios: "Agora" (default) and "Programar".
- Click "Programar" to reveal the date + time fields.
- The DATE field accepts text — typing `YYYY-MM-DD` works directly.
- The TIME field is a SCROLL-WHEEL PICKER, NOT a text input. Typing
  into it silently does nothing. To set the time:
  1. Click the time field to open the picker (two columns appear:
     hours on the left, minutes on the right).
  2. In each column, click the cell whose visible text matches the
     target value (e.g. click cell '13' in the hours column, click
     cell '10' in the minutes column). If the target value is not
     visible, scroll the column (mouse-wheel or arrow keys) until it
     appears.
  3. The minute column is in 5-minute increments only — `_validate_
     schedule_at()` snaps any user-supplied minute up to the nearest
     5 so the cell always exists.
- The submit button changes from "Postar" to "Agendar" once
  "Programar" is active. Click "Agendar", NEVER "Postar".
- TikTok rejects scheduled times less than ~20 min in the future or
  more than 10 days out.

## Anti-patterns (NEVER do these)

- DO NOT use the `write_file` or `replace_file_str` actions. No todo.md.
  No planning files. Execute steps directly — those actions waste 2-3
  steps per run and provide zero benefit.
- DO NOT click any sidebar element (Monetization, Sound Library,
  Smart Split, Inspirações). They all share the same CSS class and
  none of them help with upload.
- DO NOT call `upload_file_to_element` more than once per task.
- DO NOT click "Postar" or "Agendar" before the description has been
  typed AND the video preview is visible — the buttons are disabled
  and clicking wastes a step.
- DO NOT navigate to /tiktokstudio/upload more than once per task
  (the initial nav). Re-navigation usually means the agent is lost.
- DO NOT improvise extra steps. If the same action fails 3 times in a
  row, STOP and report — don't keep retrying.
