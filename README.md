# youthelets — face matching

Give it one face. It finds every photo that person appears in.

**Live:** <https://169-58-16-247.sslip.io/>

Point it at a pile of event photos, crop one face out of one of them, and it returns
the photos containing that person, ranked by how confident it is.

---

## Using it

Two ways to get photos in. Neither needs anything installed.

**Upload photos** — pick files from your device. No Google account, no sign-in, nothing
to configure. This always works.

**Google Drive** — sign in with your own Google account and choose photos through
Google's own picker. The app only ever receives the photos you hand it; it cannot see
the rest of your Drive.

Then: browse the gallery, click a photo containing the person you want, crop their face,
run the match. Results come back with a similarity score per photo, and you can export
the matches as a folder, a zip, or back to Drive.

Your photos are yours alone — each visitor gets their own workspace on the server, and
two people using the link at the same time never see each other's files.

---

## How the matching actually works

| Step | What does it |
|---|---|
| Find the faces in a photo | **MTCNN** (`facenet-pytorch`) |
| Turn each face into a number | **InceptionResnetV1**, vggface2 weights |
| Decide if two faces are the same person | cosine similarity ≥ **0.60** |

Everything runs locally on the server. There is no cloud vision API, no service account,
and no per-image billing.

### That 0.60 is measured, not guessed

It was calibrated on 300 same-person and 300 different-person pairs from
[LFW](https://vis-www.cs.umass.edu/lfw/), run through this exact pipeline:

- same person — 5th percentile **0.596**, median **0.793**
- different people — 99th percentile **0.419**, max **0.508**

LFW alone would suggest a lower threshold, and that would be a mistake: its images are
250px crops, and two *high-resolution* photos of different people score **0.585** through
this pipeline — above every different-person pair in LFW. 0.60 clears that with a small
buffer and still catches ~95% of true matches.

**If you change the crop, the model, or the preprocessing, re-run the calibration.** The
number is only valid for the pipeline it was measured on.

The face crop is squared with a 20% margin before resizing. Resizing a raw detection box
to 160×160 squashes the face and clips the jaw and hairline; squaring it widened the gap
between same-person and different-person scores from 0.358 to 0.404.

### What it gets wrong

Genuinely similar-looking people can still match. The closest verified false pair sits at
0.594 against a 0.60 line — a margin of 0.006. Treat the results as a shortlist, not a
verdict.

---

## Where it runs

| | |
|---|---|
| Host | `contabo` |
| Path | `/opt/youthelets`, venv at `./venv` |
| Service | `youthelets.service` (systemd) |
| Binds | `172.18.0.1:8501` — the docker bridge gateway, **not** `0.0.0.0` |
| Front door | the shared `supabase-caddy`, which terminates TLS |

Binding to the bridge gateway means the Caddy container and the host can reach the app
but the internet cannot; port 8501 is closed from outside. A single ufw rule allows
`172.18.0.0/16 → 172.18.0.1:8501` and nothing wider.

**contabo is a shared, busy box.** `almokhtar.info`, `*.almokhtar.info`,
`api.bsheel.app`, `admin.bsheel.app`, `opera.169-58-16-247.sslip.io`, the whole Supabase
stack and `hood-api` all sit behind that one Caddy. A bad reload takes them all down.
Read `CLAUDE.md` before touching it.

### Deploying a change

```bash
scp app.py contabo:/opt/youthelets/app.py
ssh contabo 'systemctl restart youthelets'
```

Then check it came back, and check the other five sites too — not just this one.

---

## Google Drive setup

Only needed for the Drive option; upload works without any of this.

The app uses the **`drive.file`** scope and Google's Picker. This is deliberate:

- `drive.file` is the only Drive scope Google classes as **non-sensitive**, so the app
  needs **no verification** and anyone can sign in — no test-user list, no warning
  screen, no 7-day expiry.
- `drive.readonly` is **restricted**: capped at 100 hand-listed users, an unverified-app
  warning for each, consent expiring weekly, and the only way out is restricted-scope
  verification plus an annual third-party security assessment ($500–$4,500/yr) on a
  domain you own.
- The trade: **you cannot list someone's Drive under `drive.file`.** A custom folder
  browser was built and then deleted for exactly this reason.

What the server needs, both in `/opt/youthelets`:

- `client_secrets.json` — an OAuth client ID of type **Web application**, redirect URI
  exactly `https://169-58-16-247.sslip.io/auth/callback`. *Not* a service account: a
  service account only ever sees folders shared with its address.
- `GOOGLE_API_KEY` in `.env` — the Picker's developer key.

Both the **Google Drive API** and the **Google Picker API** must be enabled on the
project, and the app must be **published** (Audience → Publish app) for anyone beyond
your test-user list to sign in.

Missing either file is handled cleanly: the Drive card says so up front and upload keeps
working.

---

## Layout

The app lives in [`Downloads/tiam/`](Downloads/tiam/) — an accident of how it was first
copied in, not a structure worth relying on. Anything deploying from this repo must
target that subdirectory, not the repo root.

[`Downloads/tiam/tiam.py`](Downloads/tiam/tiam.py) is the original Colab notebook this
was built from, kept as-is. It is written as a handover to someone named Tiam and is not
executed by the app.

`render.yaml`, `railway.json`, `Procfile` and `runtime.txt` are leftovers from an
abandoned Render/Railway plan. Nothing deploys from them.

- [`CLAUDE.md`](CLAUDE.md) — policy, blast radius, and the traps worth knowing
- [`FIXLOG.md`](FIXLOG.md) — every fix, with symptom, cause and how it was verified
