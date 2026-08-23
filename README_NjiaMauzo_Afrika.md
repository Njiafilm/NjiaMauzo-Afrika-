# NjiaMauzo Afrika

**Fikia Masoko, Panua Biashara**

NjiaMauzo Afrika ni jukwaa la kidijitali linalolenga kuunganisha biashara, bidhaa, masomo, huduma na fursa ndani ya Afrika na masoko ya kimataifa.

## Vipengele vya Mfumo

### 1. Soko la Bidhaa
Mfumo una sehemu ya kuonyesha bidhaa na huduma mbalimbali kama:
- Kahawa
- Korosho
- Ndizi
- Mpunga
- Alizeti
- Pamba
- Maharage
- Ufuta
- Vitunguu
- Viazi
- Mahindi

### 2. Maktaba ya Masomo
Admin anaweza kuongeza:
- Jina la somo
- Kategoria
- Maelezo
- Bei
- Chanzo cha kuaminika

**Muhimu:** Vyanzo vya masomo havionyeshwi kwa mtumiaji wa kawaida. Vinaonekana kwenye **Admin Room → Maktaba** pekee.

Admin anaweza kubonyeza:

**Fungua chanzo ↗**

ili kufungua chanzo rasmi cha somo.

### 3. Video Reels
Admin anaweza:
- Kuongeza jina la Reel
- Kuandika maelezo
- Kuchagua video kutoka kwenye kifaa
- Ku-upload video
- Ku-preview video
- Kufuta Reel

Video zilizopakiwa zinaonekana kwenye sehemu ya:

**🎬 Video Reels**

ya ukurasa wa umma.

### 4. Admin Room
Admin Room ina maeneo ya kusimamia:
- Maktaba ya Masomo
- Vyanzo vya masomo
- Video Reels
- Data ya mfumo

## Muundo wa Files

```text
NjiaMauzo_Afrika/
│
├── index.html
├── admin.html
├── app.py
├── lessons.json
├── reels.json
├── requirements.txt
├── README.md
│
└── uploads/
    └── video files
```

## Kuanza Mfumo

### 1. Sakinisha dependencies

```bash
pip install -r requirements.txt
```

### 2. Endesha Flask

Kwa development:

```bash
python app.py
```

Mfumo utapatikana kwenye:

```text
http://localhost:5000
```

### 3. Endesha kwa Gunicorn

Kwa production/hosting kama Render:

```bash
gunicorn app:app
```

## Routes

### Ukurasa wa Umma

```text
/
```

### Admin Room

```text
/admin
```

### API za Umma

```text
/api/lessons
/api/reels
```

API ya umma ya masomo **hairejeshi source/link za masomo**.

### API za Admin

```text
/api/admin/lessons
/api/admin/reels
```

Admin API ndiyo inayohifadhi na kuonyesha vyanzo vya masomo.

### Upload ya Reel

```text
POST /api/admin/reels
```

Inatumia `multipart/form-data`.

## Video Zinazoruhusiwa

- `.mp4`
- `.webm`
- `.mov`
- `.m4v`

Ukubwa wa juu uliowekwa kwenye Flask:

```text
200 MB
```

## Usalama

Katika deployment halisi inashauriwa kuongeza:
- Admin authentication/login
- Password hashing
- CSRF protection
- File scanning/validation
- Cloud storage kwa video
- Database badala ya JSON kwa data kubwa
- HTTPS
- Rate limiting

## Muhimu kwa Render

Build/Install Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn app:app
```

> Kwa video zinazopakiwa kwenye production, ni bora kutumia persistent/cloud storage kwa sababu storage ya baadhi ya hosting platforms inaweza kuwa ephemeral.

## Health Check

Mfumo una endpoint:

```text
/health
```

Inapaswa kurudisha:

```json
{
  "status": "ok",
  "service": "NjiaMauzo Afrika"
}
```

## Copyright na Vyanzo

Vyanzo vya masomo vinapaswa kuwa vya kuaminika na vya kisheria. Admin anapaswa kuweka link ya chanzo rasmi anachotumia.

## Leseni

Mradi huu ni wa **NjiaMauzo Afrika**. Usambazaji, matumizi au marekebisho ya kibiashara yafanywe kwa kufuata masharti yaliyowekwa na mmiliki wa mradi.

---

**NjiaMauzo Afrika — Fikia Masoko, Panua Biashara.**
