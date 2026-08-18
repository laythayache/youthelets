# Fix log

Newest first. One entry per real fix: symptom, root cause, fix, commit.

## 2026-08-18 — App could not run at all: no Google credentials existed

**Symptom:** every match raised `RuntimeError`; the page rendered a "Face Detection Not
Available" banner. **Root cause:** detection went through Google Cloud Vision, which needs
a service account JSON that was never on disk (only `service_account.json.template`).
**Fix:** dropped Vision entirely and switched detection to `MTCNN` from `facenet-pytorch`,
already a dependency. No credentials, no per-image billing. Verified: models load and
detect on a server with no Google configuration of any kind.

## 2026-08-18 — Different people matched each other

**Symptom:** two different women scored 0.594 against a 0.35 threshold — a false match.
**Root cause:** `SIM_THRESHOLD = 0.35` was inherited from the InsightFace era. facenet
embeddings have a different score distribution. **Fix:** calibrated on 200 same-person and
200 different-person LFW pairs through this pipeline. 0.35 gave 2.5% false matches; 0.45
gives 0% for 0.5pp more misses. Set to 0.45 with the measurement recorded in the code.

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
