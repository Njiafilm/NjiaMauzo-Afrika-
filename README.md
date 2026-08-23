# NjiaMauzo Afrika — FIXED BUILD ❶

## Marekebisho yaliyofanywa

1. **Kisanduku cha ujumbe**
   - Maandishi yanaonekana wazi kwenye background ya navy.
   - Contrast ya maandishi imeboreshwa.

2. **Maktaba ya Masomo**
   - Public page haionyeshi tena vyanzo vya masomo.
   - API ya public pia hairudishi source links kwa mtumiaji wa kawaida.
   - Admin Room > Maktaba inaendelea kuona vyanzo vya kila somo.
   - Admin anaweza kuongeza/kufuta chanzo na kukifungua kwa kubonyeza link.

3. **Video Reels**
   - Admin Room ina tab mpya **🎬 Video Reels**.
   - Admin anaweza kuchagua video.
   - Kuna preview kabla ya upload.
   - Video inaweza kufutwa baadaye.
   - Video zilizopakiwa zinahifadhiwa kwenye `static/uploads/reels/`.
   - Public page inazipakia kupitia `/api/reels`.
   - Video: MP4, WebM, MOV, M4V.
   - Kikomo: 200MB.

4. **Backend**
   - API mpya:
     - `GET /api/reels`
     - `GET /api/admin/reels`
     - `POST /api/admin/reels`
     - `DELETE /api/admin/reels/<id>`
   - `Werkzeug` imeongezwa kwa `secure_filename`.
   - Flask upload limit imepandishwa hadi 200MB.

## Render

Install:
```bash
pip install -r requirements.txt
```

Start:
```bash
gunicorn app:app
```

> Kumbuka: video zilizopakiwa kwenye storage ya kawaida ya Render zinaweza kupotea wakati wa redeploy/restart ikiwa huna persistent disk au cloud storage.
