# Face Matching System

The app itself. See the [root README](../../README.md) for what it does and how the
matching works, and [GUIDE.md](GUIDE.md) for running, deploying and debugging it.

Live at <https://169-58-16-247.sslip.io/>.

## Quick start

```bash
python -m venv venv
./venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Install torch from the CPU index first, or pip drags in ~2.5 GB of unused CUDA wheels.
Then visit <http://localhost:5000>. Upload works straight away; Google Drive does not
locally, because the OAuth redirect URI is registered against the live host.
