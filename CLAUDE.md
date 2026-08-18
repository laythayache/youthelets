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
- **`SIM_THRESHOLD` is calibrated, not chosen.** 0.60, measured on 300 same-person and
  300 different-person LFW pairs through this exact pipeline. If you change the crop, the
  model, or the preprocessing, re-run that calibration — the number is only valid for the
  pipeline it was measured on.
- **LFW alone will mislead you.** Its 250px crops put the different-person maximum at 0.508,
  but two high-resolution photos of different people reach 0.585 through this pipeline. Any
  threshold picked from LFW without a high-resolution check will be too permissive.
- The crop squares the detection box and adds 20% margin before resizing to 160x160.
  Resizing the raw box distorts the face and drops the jaw and hairline; squaring it widened
  the same-vs-different gap from 0.358 to 0.404.
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

Uses the **drive.file** scope only, and Google's **Picker**. This is deliberate and
should not be widened back to `drive.readonly`:

- `drive.file` is the only Drive scope Google classes as **non-sensitive**, and apps
  using only non-sensitive scopes need **no verification**. Anyone can sign in, with no
  warning screen and no expiry.
- `drive.readonly` is **restricted**: 100 hand-listed test users, an unverified-app
  warning, consent expiring every 7 days, and the only escape is restricted-scope
  verification plus an annual third-party security assessment ($500-$4,500/yr) on a
  domain you own. `169-58-16-247.sslip.io` would not qualify.
- The consequence: **you cannot list a visitor's Drive under `drive.file`.** A custom
  folder browser was built and then removed for exactly this reason. Google's Picker is
  the sanctioned way in, and the app only sees what the visitor picks.

Needs two things in `/opt/youthelets`:
- `client_secrets.json` - the OAuth **client ID** (Web application), redirect URI
  `https://169-58-16-247.sslip.io/auth/callback`. Not a service account: a service
  account only sees folders shared with its address and cannot browse a Drive at all.
- `GOOGLE_API_KEY` in `.env` - the Picker's developerKey. The **Google Picker API** and
  the **Google Drive API** must both be enabled on the project.

Without either, `/auth` and `/api/drive/picker-config` return a clean explanation and
the Drive card says so up front; upload still works.

**Open question, unresolved in Google's own docs:** whether picking a *folder* in the
Picker extends `drive.file` access to the files inside it. `/api/drive/import` counts
folders it cannot open and tells the visitor to select the photos instead, rather than
failing the whole import. Settle this the first time a real Drive is connected.
