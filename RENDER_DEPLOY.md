# Deploy NjiaMauzo Afrika on Render

**Live URL:** https://njiamauzo-afrika.onrender.com  
**Repo:** https://github.com/Njiafilm/NjiaMauzo-Afrika-

## Option A — Connect existing service (recommended if URL already exists)

1. Fungua [https://dashboard.render.com](https://dashboard.render.com)
2. Chagua service **njiamauzo-afrika** (au unda mpya)
3. **Settings → Build & Deploy**
   - **Repository:** `https://github.com/Njiafilm/NjiaMauzo-Afrika-`
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
4. **Environment** — ongeza:

| Key | Value |
|-----|--------|
| `SECRET_KEY` | (string ndefu ya siri) |
| `PASSWORD_SALT` | (string ya siri) |
| `FLASK_DEBUG` | `0` |
| `APP_URL` | `https://njiamauzo-afrika.onrender.com` |
| `INFO_EMAIL` | `info@njiamauzo.africa` |
| `PYTHON_VERSION` | `3.12.8` |

5. **Manual Deploy → Deploy latest commit**

## Option B — New Web Service from GitHub

1. Dashboard → **New +** → **Web Service**
2. Connect GitHub account → chagua **Njiafilm/NjiaMauzo-Afrika-**
3. Jaza:
   - **Name:** `njiamauzo-afrika`
   - **Region:** Oregon (au karibu nawe)
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Instance:** Free
4. Ongeza Environment Variables (meza hapo juu)
5. **Create Web Service**

## Option C — Blueprint (render.yaml)

1. Dashboard → **New +** → **Blueprint**
2. Connect repo `NjiaMauzo-Afrika-`
3. Render itasoma `render.yaml` na kuunda service

## Baada ya deploy

- Site: https://njiamauzo-afrika.onrender.com
- Admin: https://njiamauzo-afrika.onrender.com/admin  
  - Email: `admin@njiamauzo.africa`  
  - Password: `0000` (**badilisha mara moja**)

## Notes

- Free tier: service inaweza "sleep" baada ya dakika 15 bila traffic
- SQLite kwenye free plan data inaweza kupotea kwenye redeploy — production tumia PostgreSQL
- Kila `git push` kwenye `main` → auto deploy (kama Auto-Deploy = Yes)
