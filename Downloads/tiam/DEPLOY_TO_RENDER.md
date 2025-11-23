# 🚀 Deploy Face Matching System to Render.com

## Quick Setup Guide - Auto-Load from Your Google Drive

This guide will help you deploy your Face Matching System so it automatically loads images from your Google Drive folder.

---

## 📋 Prerequisites

Before starting, you need:

1. ✅ **Google Drive Folder ID** - The folder containing your images
2. ✅ **Service Account JSON** - Already have `service_account.json` in your project
3. ✅ **GitHub Account** - To push your code
4. ✅ **Render Account** - Free signup at render.com

---

## Step 1: Get Your Google Drive Folder ID

1. Open Google Drive in your browser
2. Navigate to the folder you want to use
3. Right-click the folder → **Get link** or click the folder → Click the link icon
4. Copy the URL - it looks like:
   ```
   https://drive.google.com/drive/folders/1XaEwtA5mh0Z3Nkf9NQ12m9GzJbD2kbcQ
   ```
5. **Extract the Folder ID** - Everything after `/folders/`:
   ```
   1XaEwtA5mh0Z3Nkf9NQ12m9GzJbD2kbcQ
   ```

**📝 Write down this Folder ID - you'll need it in Step 4**

---

## Step 2: Share Folder with Service Account

Your `service_account.json` contains a service account email. You need to share your Drive folder with it:

1. Open `service_account.json` in a text editor
2. Find the `"client_email"` field - it looks like:
   ```json
   "client_email": "drive-photo-bot@youthletes.iam.gserviceaccount.com"
   ```
3. Copy that email address
4. Go back to Google Drive
5. Right-click your folder → **Share**
6. Paste the service account email
7. Give it **Viewer** access (read-only is enough)
8. Click **Send** (you can uncheck "Notify people")

---

## Step 3: Push Code to GitHub

If you haven't already:

```bash
# Navigate to your project
cd C:\Users\Aligned\Downloads\tiam

# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Ready for deployment to Render"

# Create repository on GitHub.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

**⚠️ Important**: Make sure `service_account.json` is in `.gitignore` (it should be already)

---

## Step 4: Deploy on Render.com

### 4.1 Create Account & Service

1. Go to [render.com](https://render.com)
2. Sign up (free) - use GitHub to sign in
3. Click **"New +"** → **"Web Service"**
4. Connect your GitHub account if prompted
5. Select your repository

### 4.2 Configure Service

Fill in these settings:

| Setting | Value |
|---------|-------|
| **Name** | `face-matching-app` (or any name you like) |
| **Environment** | `Python 3` |
| **Region** | Choose closest to you |
| **Branch** | `main` |
| **Root Directory** | (leave empty) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 200` |
| **Plan** | **Free** |

### 4.3 Add Environment Variables

Click **"Environment"** tab and add these variables:

| Key | Value | Notes |
|-----|-------|-------|
| `SECRET_KEY` | Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` | Run this locally first |
| `FLASK_ENV` | `production` | |
| `YOUTHELETES_DRIVE_FOLDER_ID` | **Your folder ID from Step 1** | The ID you extracted |
| `SERVICE_ACCOUNT_FILE` | `service_account.json` | (optional, this is default) |

**To generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output and paste it as the value for `SECRET_KEY`.

### 4.4 Upload service_account.json

Since `service_account.json` is in `.gitignore`, you need to upload it separately:

1. In Render dashboard, go to your service
2. Click **"Environment"** tab
3. Scroll down to **"Secret Files"** section
4. Click **"Add Secret File"**
5. **Name**: `service_account.json`
6. **Contents**: Copy and paste the entire contents of your local `service_account.json` file
7. Click **"Save"**

### 4.5 Deploy

1. Click **"Create Web Service"** at the bottom
2. Wait 10-15 minutes for first deployment
   - First time downloads InsightFace models (~500MB)
   - You'll see build logs in real-time
3. Once deployed, you'll get a URL like: `https://face-matching-app.onrender.com`

---

## Step 5: Test Your Deployment

1. Visit your Render URL
2. The app should automatically load images from your Google Drive folder
3. If you see an error, check the **Logs** tab in Render dashboard

---

## 🔧 Troubleshooting

### Build Fails
- Check **Logs** tab for specific errors
- Verify `requirements.txt` is correct
- Check Python version (should be 3.11)

### App Crashes
- Check **Logs** tab
- Verify `SECRET_KEY` is set
- Verify `YOUTHELETES_DRIVE_FOLDER_ID` is correct
- Verify `service_account.json` was uploaded correctly

### Can't Access Drive
- Verify folder is shared with service account email
- Verify folder ID is correct
- Check service account has proper permissions

### Slow Performance
- Free tier has limited resources
- First request after spin-down takes ~30 seconds
- Face matching is CPU-intensive - be patient

### Models Not Loading
- First deployment takes 10-15 minutes (downloading models)
- Check logs for download progress
- Ensure sufficient disk space

---

## ✅ After Deployment

Your app is now live! 

**Features:**
- ✅ Automatically loads from your Google Drive folder
- ✅ No manual folder selection needed
- ✅ Accessible to anyone with the URL
- ✅ Free hosting (with limitations)

**Limitations of Free Tier:**
- Spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds
- Limited CPU/memory (face matching may be slow)

---

## 🎉 You're Done!

Your Face Matching System is now hosted and accessible to everyone!

**Next Steps:**
- Share the URL with users
- Monitor usage in Render dashboard
- Consider upgrading to paid tier for better performance

---

## 📞 Need Help?

- Check Render logs for errors
- Verify all environment variables are set
- Test locally first if issues occur
- See `GUIDE.md` for more troubleshooting

