# NjiaMauzo Admin Room Update

## Kilichoongezwa
- Masoko + Agent Hub ndani ya Admin Room.
- Sources za partnership/agent: HACO Industries, Johana Products Rwanda, KUTRE East Africa Industries na Rwanda Trade Portal.
- Chumba binafsi cha kila Admin kupitia `🏠 Chumba Changu`.
- Mkurugenzi anaweza kufungua chumba cha Admin mwingine; ukaguzi unaandikwa kwenye Audit Log.
- Create Account ndani ya Uongozi: Admin, Mhasibu na Mkurugenzi.
- Kikomo cha akaunti 15; Mkurugenzi 1 na Mhasibu 1.
- Password lazima iwe na angalau herufi 10.
- Mkurugenzi pekee ndiye anayeruhusiwa kuunda/kusimamia akaunti.

## Backend endpoints
- POST `/api/admin/accounts`
- GET `/api/admin/my-room`
- GET `/api/admin/accounts/<id>/room`

## Muhimu
Akaunti za sasa 15 zinaendelea kuseed kutoka environment variables. Create Account haitaruhusu akaunti ya 16.
