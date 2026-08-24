# NjiaMauzo Afrika — rebuilt files

Files: `index.html`, `app.py`, `admin.html`, `requirements.txt`.

Muhimu:
- Payment access ni server-side na product-specific: malipo ya bidhaa A hayafungui bidhaa B.
- Seller contact, seller URL, source URL na price vinafichwa hadi payment ya bidhaa husika ithibitishwe.
- Mkurugenzi na Mhasibu pekee wanathibitisha malipo.
- Admin accounts zina kikomo cha 15; kila admin ana role/chumba chake.
- Reels, Uongozi, Audit, Chat, Masoko & Agent na payment endpoints zipo.
- Factory products zinaonekana kwenye section ya kiwandani, Takwimu na Live Activity Feed.
- Director supervisory access ni ya mamlaka na audit-logged; hakuna hidden/backdoor login.
- Badilisha default passwords na `SECRET_KEY` kabla ya production.

Default accounts za first run:
- director / NjiaMauzoDirector2026!
- accountant / NjiaMauzoMhasibu2026!

## Marekebisho ya sasa
- `index.html` imehifadhi muundo wa sasa; sehemu ya Masoko & Agent/maombi ya uwakala haionekani kwa mteja wa kawaida.
- `admin.html` ndiyo sehemu ya kusimamia Masoko & Agent na kuona maombi ya uwakala.
- `app.py` imeongezewa endpoints zinazotumiwa na Admin Room: accounts, dashboard, payments, markets, reels, chat na audit.
- Admin accounts zina kikomo cha 15; Director na Accountant wana roles maalum.
