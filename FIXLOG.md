# Fix log

Newest first. One entry per real fix: symptom, root cause, fix, commit.

## 2026-08-18 — App could not run at all: no Google credentials existed

**Symptom:** every match raised `RuntimeError`; the page rendered a "Face Detection Not
Available" banner. **Root cause:** detection went through Google Cloud Vision, which needs
a service account JSON that was never on disk (only `service_account.json.template`).
**Fix:** dropped Vision entirely and switched detection to `MTCNN` from `facenet-pytorch`,
already a dependency. No credentials, no per-image billing. Verified: models load and
detect on a server with no Google configuration of any kind.

## 2026-08-18 — Different people matched each other (revised twice)

**Symptom:** two different women (Jolie / Siegel press photos) scored 0.594 against a 0.35
threshold — a false match. **Root cause:** `SIM_THRESHOLD = 0.35` was inherited from the
InsightFace era; facenet embeddings score differently. **First fix** set 0.45 from 200+200 LFW
pairs. **That was not enough** — the same pair still matched at 0.586, because LFW's 250px crops
under-represent the hard tail: its different-person max was 0.508, while real high-resolution
photos of different people reach 0.585.

**Second cause found while investigating:** the crop resized a non-square detection box straight
to 160x160, squashing the face, and clipped the jaw and hairline. Squaring the box with a 20%
margin widened the same-vs-different gap from 0.358 to 0.404.

**Final fix:** square+margin crop, and `SIM_THRESHOLD = 0.60` calibrated on 300+300 LFW pairs
through the shipped pipeline (same-person p5 0.596 / p10 0.653 / median 0.793; different-person
p99 0.419 / max 0.508). 0.60 clears the known hard pair (0.585) with a buffer and still catches
~95% of true matches. Verified end-to-end through the live URL: 5/5 of the right person found,
0 false matches, and the Jolie/Siegel pair now correctly rejected at 0.594.

**Note the margin is thin** — that pair sits 0.006 below the line. Photos of genuinely similar
people can still slip through. Re-run the calibration if the crop, model or preprocessing changes.

## 2026-08-18 — Two visitors would overwrite each other's results

**Symptom:** not yet observed; found before sharing the link. **Root cause:** matching wrote a
single shared `output/matches.csv`, and export read it back. Two people using the link at once
means the second run overwrites the first, and export then hands over the wrong person's photos.
**Fix:** `session_results_csv()` — one results file per visitor, matching the per-session upload
and Drive-download folders.

## 2026-08-18 — Result badges contradicted the verdict beside them

**Symptom:** a row could show an amber "medium" similarity badge next to a green "✓ Match".
**Root cause:** the front end hardcoded 0.35/0.5 for colouring while the server matched on
`SIM_THRESHOLD`. **Fix:** the API now returns `threshold` and the client colours against it.

## 2026-08-18 — Anyone with the link could read files off the server

**Symptom:** `/api/image?path=` accepted any absolute path; `/api/images/scan` walked any
directory. On contabo that box also runs Supabase, almokhtar.info and bsheel.app.
**Root cause:** no containment on client-supplied paths — absence of a check was treated as
permission. **Fix:** `safe_path()` resolves every incoming path and refuses anything outside
`uploads/`/`output/`; `load_bgr` and `scan_images` call it. Proven both halves: blocks
`/etc/passwd` and `uploads/../../etc/shadow`, allows a real upload.

## 2026-08-18 — No way for a visitor to supply photos

**Symptom:** a shared link was unusable by anyone but the owner — the only inputs were a
Google Drive folder or a directory already on the server. **Fix:** added
`POST /api/images/upload` plus the front-end control, saving into a per-session folder so
two visitors never see each other's photos. Drive downloads made per-session for the same
reason.

## 2026-08-18 — OAuth redirect would have been rejected by Google

**Symptom:** not yet visible (Drive unconfigured), found before shipping. **Root cause:**
`request.url_root` behind Caddy resolved to the internal bind address, so the
`redirect_uri` sent to Google was `http://172.18.0.1:8501/auth/callback`. **Fix:**
`ProxyFix(x_for, x_proto, x_host)`. Verified through the live URL: Google now receives
`https://169-58-16-247.sslip.io/auth/callback`.

## 2026-08-18 — Install could not have succeeded

**Symptom:** would have failed on any clean deploy. **Root cause:** `requirements.txt` was
UTF-16 encoded, and pinned `torchvision==0.16.0` against `torch==2.9.1` — an impossible
pair. **Fix:** rewritten as UTF-8, `torchvision==0.24.1`. Verified by a real install on
contabo (`torch-2.9.1+cpu`, `torchvision-0.24.1+cpu`).

## 2026-08-18 — Caddy could not reach the app (502)

**Symptom:** `https://169-58-16-247.sslip.io/` returned 502 with a valid certificate.
**Root cause:** ufw was dropping traffic from the docker bridge to the host port.
**Fix:** `ufw allow from 172.18.0.0/16 to 172.18.0.1 port 8501 proto tcp`. Verified 200
from an external machine, and port 8501 still refused from the internet.
