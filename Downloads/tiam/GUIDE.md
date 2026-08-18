# Operator guide

Everything a person needs to run, deploy or debug this. For what the app *is* and how the
matching works, see the [root README](../../README.md).

---

## Running it locally

```bash
python -m venv venv
./venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Install torch from the CPU index **first**. Installing it from PyPI on Linux drags in
~2.5 GB of CUDA wheels that are never used.

Visit <http://localhost:5000>. On first run it downloads ~107 MB of vggface2 weights.

Upload works immediately. Google Drive will not — the redirect URI is registered against
the live host, not localhost.

---

## Deploying

```bash
scp app.py contabo:/opt/youthelets/app.py
ssh contabo 'systemctl restart youthelets'
```

Static files and templates the same way, into `static/` and `templates/`.

Then verify — and not only this app. contabo is shared:

```bash
ssh contabo 'for h in api.bsheel.app admin.bsheel.app opera.169-58-16-247.sslip.io \
  almokhtar.info www.almokhtar.info 169-58-16-247.sslip.io; do \
  printf "%-34s %s\n" "$h" "$(curl -s -o /dev/null -w "%{http_code}" https://$h/)"; done'
```

Expected: `200 401 200 200 301 200`. The 401 on `admin.bsheel.app` is its basic auth, not
a fault.

### If you must touch the Caddyfile

It is at `/root/supabase-docker/volumes/proxy/caddy/Caddyfile` and it fronts six
hostnames plus the Supabase stack. Back it up, validate, then reload — never reload on
hope:

```bash
cp Caddyfile Caddyfile.bak.$(date +%s)
docker exec supabase-caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec supabase-caddy caddy reload   --config /etc/caddy/Caddyfile --adapter caddyfile
```

TLS on this box is on-demand and gated by an app, not by the Caddyfile. Adding a hostname
to Caddy is **not enough** — `hood-api` decides whether a certificate is issued. Check
first; it costs nothing:

```bash
docker exec supabase-caddy wget -qO- "http://hood-api:8090/api/tls/ask?domain=<host>"
```

200 means it will issue, 404 means it never will and the site will simply never answer.
Changing that list means recreating the `hood-api` container, which drops almokhtar's API.

---

## Google setup, start to finish

Only needed for the Drive option. Upload works with none of it.

1. **Google Cloud Console → new project.**
2. **APIs & Services → Library** → enable **Google Drive API** *and* **Google Picker API**.
3. **Google Auth Platform → Branding** → fill in app name and support email.
4. **Credentials → Create credentials → OAuth client ID → Web application.**
   Authorised redirect URI, exactly:
   `https://169-58-16-247.sslip.io/auth/callback`
   Download the JSON to `/opt/youthelets/client_secrets.json`, `chmod 600`.
   **Web application, not Desktop app** — Desktop has no redirect URI and will not work.
5. **Credentials → Create credentials → API key.** Put it in `/opt/youthelets/.env` as
   `GOOGLE_API_KEY=...`. Restrict it by HTTP referrer to `https://169-58-16-247.sslip.io/*`.
   This key is handed to the browser by design, so treat it as public but rate-limited.
6. **Google Auth Platform → Audience → Publish app.** Until you do, only hand-listed test
   users can sign in. Because the app requests only `drive.file` — a non-sensitive scope —
   publishing needs no verification.

Restart the service after adding either file.

### Why not a service account

A service account only ever sees folders explicitly shared with its email address. It
cannot browse anyone's Drive, so it cannot serve this. It was considered and rejected.

### Why not `drive.readonly`

It is a **restricted** scope: 100 hand-listed users, an unverified-app warning for each,
consent expiring every 7 days, and the only escape is restricted-scope verification plus
an annual third-party security assessment ($500–$4,500/yr) on a domain you own.
`sslip.io` is not ours, so it would not qualify.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `/auth` returns 400, "credentials not configured" | no `client_secrets.json` on the server |
| Drive card says "Not set up on this server yet" | `client_secrets.json` **or** `GOOGLE_API_KEY` missing — it needs both |
| `redirect_uri_mismatch` | the URI in the console does not match character for character. No trailing slash, `https` not `http` |
| "Access blocked … has not completed verification" | app still in Testing and the user is not on the test-user list. Publish it |
| Sign-in works, then every Drive call fails | Google Drive API not enabled on the project |
| Picker never opens | Google Picker API not enabled, or the API key is missing or referrer-restricted to the wrong host |
| 502 from the public URL | the app is down, or ufw is blocking the Caddy container. Rule needed: `ufw allow from 172.18.0.0/16 to 172.18.0.1 port 8501 proto tcp` |
| Valid certificate but the host never answers | `/api/tls/ask` is refusing that hostname — see above |
| "No reference face set" at random | more than one gunicorn worker. Reference embeddings live in process memory; keep it at one worker |
| Uploaded iPhone photos all skipped | `.heic` is not supported. The page reports the skipped count rather than failing silently |

Logs: `journalctl -u youthelets -f`

---

## Things that look right and are not

**`MTCNN.extract()`** looks like the correct way to crop a detected face. With
`post_process=False` it skips prewhitening and every embedding collapses to ~0.98
similarity — matching everyone with everyone. The manual crop through `preprocess` is
deliberate. Measured, not guessed.

**Calibrating the threshold on LFW alone.** Its 250px crops put the different-person
maximum at 0.508, but two high-resolution photos of different people reach 0.585 through
this pipeline. Any threshold picked from LFW without a high-resolution check is too
permissive.

**Two gunicorn workers.** The Procfile once said `--workers 2`. Reference embeddings are
per-process, so a visitor who set a face on one worker and matched on the other got a
bare "No reference face set".

**Trusting `request.url_root` behind Caddy.** Without `ProxyFix` it resolves to the
internal bind address, and the `redirect_uri` sent to Google is one it will never accept.

---

## Layout

```
app.py                  the whole application, ~1100 lines
templates/index.html    single page, five steps
static/js/app.js        front end
static/css/style.css    styling
tiam.py                 the original Colab notebook, kept as-is, not executed
.env                    SECRET_KEY and GOOGLE_API_KEY (chmod 600, never committed)
client_secrets.json     OAuth client (chmod 600, gitignored)
```

`render.yaml`, `railway.json`, `Procfile`, `runtime.txt` are leftovers from an abandoned
Render/Railway plan. Nothing deploys from them.
