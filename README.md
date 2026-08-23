# NjiaMauzo Afrika — FIXED 3

## Render error iliyorekebishwa

Error iliyokuwa kwenye log:

`NameError: name 'UPLOAD_DIR' is not defined`

Chanzo kilikuwa `REELS_DIR = UPLOAD_DIR / "reels"` kilitekelezwa wakati `app.py` inapoload, kabla `UPLOAD_DIR` haijaelezwa.

### Marekebisho
- `UPLOAD_DIR` sasa inawekwa mara moja baada ya kuundwa kwa Flask app, kabla ya routes/blocks zote zinazotumia upload storage.
- Definition ya zamani ya `UPLOAD_DIR` imeondolewa ili kusiwe na duplicate.
- Video Reels API zinaendelea kutumia `UPLOAD_DIR / "reels"` bila NameError.
- `requirements.txt` ina Flask, flask-cors, gunicorn na Werkzeug.
- `render.yaml` ina build/start/health-check commands.
- `index.html` na `admin.html` zimehifadhiwa pamoja na marekebisho ya public/admin UI.

## Render
Build:
```bash
pip install -r requirements.txt
```

Start:
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Health check:
```text
/health
```

## Reels
Admin API:
- `GET /api/admin/reels`
- `POST /api/admin/reels`
- `DELETE /api/admin/reels/<id>`

Public API:
- `GET /api/reels`

Video files zinawekwa kwenye:
```text
static/uploads/reels/
```

> Kwa production, tumia Persistent Disk au cloud object storage kwa video ikiwa hosting yako ina ephemeral filesystem.
