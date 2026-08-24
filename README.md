# NjiaMauzo Afrika — Endpoints Update

Imeongezwa bila kubadilisha structure kuu ya index.html:

- `/api/reels` GET/POST na `/api/reels/<id>` DELETE kwa tab ya Reels.
- Akaunti 15 za Admin: Mkurugenzi Mkuu 1, Mhasibu 1, Admin 13.
- `/api/admin/accounts` na management endpoints.
- `/api/admin/reports` kwa taarifa za Admin kwenda kwa Mhasibu + Mkurugenzi.
- `/api/admin/audit-log` kwa Mkurugenzi/Mhasibu.
- Director-only account review/reset/toggle; review inaingia audit log bila kumjulisha target admin.
- `index.html` iliyotumika ni ile yenye SOKO LETU, marketplace ya safu mbili, na `#nmContextChat`; haijabadilishwa kuwa index-91.
- `admin_room.html` ina tabs za Reels, Uongozi, Chat na Public Preview.

## Credentials

Kwa usalama, badilisha credentials za default kupitia Render Environment Variables:

- `ADMIN_DIRECTOR_USER`, `ADMIN_DIRECTOR_PASS`, `ADMIN_DIRECTOR_EMAIL`
- `ADMIN_ACCOUNTANT_USER`, `ADMIN_ACCOUNTANT_PASS`, `ADMIN_ACCOUNTANT_EMAIL`
- `ADMIN_1_USER` ... `ADMIN_13_USER`
- `ADMIN_1_PASS` ... `ADMIN_13_PASS`
- `ADMIN_1_NAME` ... `ADMIN_13_NAME`
- `ADMIN_1_EMAIL` ... `ADMIN_13_EMAIL`

Default values zipo kwa bootstrap tu; usizitumie production.
