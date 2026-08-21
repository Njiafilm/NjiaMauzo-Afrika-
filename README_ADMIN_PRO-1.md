# NjiaMauzo Afrika — Admin Pro Dashboard

## Kilichoboreshwa
- Admin Room imebadilishwa kuwa **Full Admin Control Center** yenye sidebar + responsive dashboard.
- Overview inaonyesha live visitors, visits za leo, bidhaa, pending orders, active ads na blocked users.
- Payment orders na advisory orders zinaonekana pamoja na verify actions.
- Product Market, Ads/Engagement, AI Search Center, User Moderation, Recent Discussions na System/Network vimewekwa ndani ya dashboard moja.
- Dashboard hutumia adaptive polling: mtandao ukiwa 2G/save-data, refresh inapungua ili kupunguza matumizi ya data; mtandao ukiwa mzuri refresh huwa ya haraka.
- Browser Network Information API huonyesha effective connection type, downlink estimate, RTT na online/offline state pale browser inapotoa taarifa hizo.
- Backend `after_request` imeongezwa gzip compression kwa responses kubwa za JSON/HTML/CSS/JavaScript, hivyo kupunguza ukubwa wa data unaopakuliwa kwenye mobile/slow networks.

## Usalama
- Admin dashboard bado inalindwa na session ya `is_admin` kwenye backend.
- POST/DELETE admin actions hutuma CSRF token.
- Hakuna password ya admin iliyowekwa ndani ya dashboard hii.

## Faili
- `admin.html` — dashboard mpya.
- `app-57.py` — backend pamoja na gzip response compression.
- `index-60.html` — UI ya main site iliyoboreshwa awali.
