# youthelets

Face matching web app. Give it one reference face, point it at a pile of photos,
it returns every photo that person appears in.

The app lives in `Downloads/tiam/` — an accident of how it was first copied in, not a
structure worth relying on. Anything that deploys from this repo must target that
subdirectory, not the repo root.

## Policy

Mirror of the entry in `C:\Users\user\.claude\memory\policies.md`. If the two disagree,
say so out loud rather than picking one.

- **branch:** commit straight to `main`. No branch needed.
- **push:** yes, push to `main` freely.
- **deploy:** ssh to `contabo`, `rsync`/`scp` into `/opt/youthelets`, `systemctl restart youthelets`.
- **server:** `contabo` — hand-editable for this app's own files and its own systemd unit.
  **The shared `supabase-caddy` Caddyfile is not freely editable** (see blast radius).
- **who runs it:** Claude ssh's in and does it. Never hand Layth a line to paste.
- **blast radius:** contabo is shared and busy. `almokhtar.info`, `*.almokhtar.info`,
  `www.almokhtar.info`, `api.bsheel.app`, `admin.bsheel.app`,
  `opera.169-58-16-247.sslip.io`, the whole Supabase stack and `hood-api` all sit behind
  one Caddy on :80/:443. A bad reload takes all of them down.
- **status:** confirmed 2026-08-18 by Layth.

## Where it runs

- URL: <https://169-58-16-247.sslip.io/>
- Path: `/opt/youthelets`, venv at `./venv`, service `youthelets.service`
- Binds `172.18.0.1:8501` — the `supabase_default` bridge gateway. Deliberately not
  `0.0.0.0`: the Caddy container and the host can reach it, the internet cannot.
  A ufw rule allows `172.18.0.0/16 -> 172.18.0.1:8501` and nothing wider.
- TLS is on-demand, gated by `hood-api`'s `/api/tls/ask`. The bare host
  `169-58-16-247.sslip.io` was **already** in that container's `RESERVED_HOSTS`, which is
  why adding this site needed no change to `hood-api`. Do not assume a new hostname is
  free — check `RESERVED_HOSTS` first, or the certificate will never issue.
- Caddyfile: `/root/supabase-docker/volumes/proxy/caddy/Caddyfile`,
  backup `Caddyfile.bak.pre-youthelets`.

## Face matching specifics

- Detection is **MTCNN**, embeddings are **facenet-pytorch InceptionResnetV1 (vggface2)**.
  Both run locally. There is no Google Cloud Vision and no service account — do not
  reintroduce one, it costs money per image and buys nothing here.
- **`SIM_THRESHOLD` is calibrated, not chosen.** 0.45, measured on 200 same-person and
  200 different-person LFW pairs through this exact pipeline. If you change the crop, the
  model, or the preprocessing, re-run that calibration — the number is only valid for the
  pipeline it was measured on.
- `MTCNN.extract()` looks like the right way to crop and is **wrong here**: with
  `post_process=False` it skips prewhitening and every embedding collapses to ~0.98
  similarity, matching everyone with everyone. The manual crop through `preprocess` is
  deliberate.
- Reference embeddings live in a per-process dict, so gunicorn runs **one worker** with
  threads. Two workers means "no reference face set" errors at random.

## Paths from the browser are hostile

`safe_path()` gates every client-supplied path to the app's own `uploads/` and `output/`.
Before it existed, `/api/image?path=` would read any image on the box and
`/api/images/scan` would list any directory — on a server that also runs Supabase,
almokhtar and bsheel. Keep it fail-closed: no allowed root matched means refuse.

## Google Drive

The Drive flow needs `client_secrets.json` (an OAuth **client ID**, not a service
account) in `/opt/youthelets`. Without it `/auth` returns a clean 400 and the rest of
the app still works via upload. Redirect URI must be registered as
`https://169-58-16-247.sslip.io/auth/callback`.
