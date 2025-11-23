# ✅ Quick Deployment Checklist

## Before You Start

You need these 3 things:

1. **Google Drive Folder ID** - Your root folder containing images
2. **service_account.json** - Already in your project ✅
3. **GitHub Repository** - To push your code

---

## Step-by-Step Deployment

### 1️⃣ Get Your Google Drive Folder ID

1. Open Google Drive → Navigate to your folder
2. Right-click folder → **Get link**
3. Copy the URL
4. Extract the ID (everything after `/folders/`)
   - Example: `https://drive.google.com/drive/folders/1ABC123xyz`
   - Folder ID: `1ABC123xyz`

**📝 Write it down: `_________________________`**

---

### 2️⃣ Share Folder with Service Account

1. Open `service_account.json`
2. Find `"client_email"` - copy that email
3. Go to Google Drive → Right-click your folder → **Share**
4. Paste the service account email → **Viewer** access → **Send**

---

### 3️⃣ Push to GitHub

```bash
cd C:\Users\Aligned\Downloads\tiam
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

---

### 4️⃣ Deploy on Render

1. Go to [render.com](https://render.com) → Sign up
2. **New +** → **Web Service** → Connect GitHub → Select repo
3. **Settings:**
   - Name: `face-matching-app`
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 200`
   - Plan: **Free**
4. **Environment Variables:**
   - `SECRET_KEY` = (run: `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `FLASK_ENV` = `production`
   - `YOUTHELETES_DRIVE_FOLDER_ID` = **Your folder ID from step 1**
5. **Secret Files:**
   - Name: `service_account.json`
   - Contents: Copy entire content of your local `service_account.json`
6. Click **Create Web Service**
7. Wait 10-15 minutes ⏳

---

### 5️⃣ Test

Visit your Render URL → Images should auto-load! 🎉

---

## ✅ Done!

Your app is now live and accessible to everyone!

**See `DEPLOY_TO_RENDER.md` for detailed instructions.**

