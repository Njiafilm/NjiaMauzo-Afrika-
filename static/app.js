/* ═══════════════════════════════════════════════════
   NjiaMauzo Afrika Pro — Frontend Logic
   ═══════════════════════════════════════════════════ */

let currentUser = null;
let currentListingId = null;
let userLat = null;
let userLon = null;

// ── HELPERS ──────────────────────────────────────
async function api(url, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin'
  };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(url, opts);
    return await res.json();
  } catch (e) {
    console.error(e);
    return { error: 'Network error' };
  }
}

function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'sasa hivi';
    if (diff < 3600) return Math.floor(diff / 60) + 'm';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h';
    return d.toLocaleDateString('sw-TZ', { day: 'numeric', month: 'short' });
  } catch {
    return iso.slice(0, 10);
  }
}

function toast(msg, isError = false) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle('error', isError);
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3200);
}

function openModal(id) {
  document.getElementById(id)?.classList.remove('hidden');
}
function closeModal(id) {
  document.getElementById(id)?.classList.add('hidden');
}

function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  const el = document.getElementById('section-' + name);
  if (el) el.classList.add('active');

  // Close mobile nav
  document.getElementById('navLinks')?.classList.remove('open');

  if (name === 'marketplace') loadListings();
  if (name === 'prices') loadPrices();
  if (name === 'live') loadLive();
  if (name === 'home') loadStats();
}

function toggleMobileNav() {
  document.getElementById('navLinks')?.classList.toggle('open');
}

// ── AUTH ─────────────────────────────────────────
async function checkAuth() {
  const me = await api('/api/me');
  currentUser = me.logged_in ? me : null;
  updateAuthUI();
}

function updateAuthUI() {
  const authArea = document.getElementById('authArea');
  const userArea = document.getElementById('userArea');
  const adminLink = document.getElementById('adminLink');
  const btnAdd = document.getElementById('btnAddListing');

  if (currentUser) {
    authArea?.classList.add('hidden');
    userArea?.classList.remove('hidden');
    const chip = document.getElementById('userChip');
    if (chip) chip.textContent = currentUser.name + (currentUser.is_verified ? ' ✓' : '');
    if (adminLink) {
      adminLink.classList.toggle('hidden', !currentUser.is_admin);
    }
    if (btnAdd) btnAdd.style.display = '';
  } else {
    authArea?.classList.remove('hidden');
    userArea?.classList.add('hidden');
    if (btnAdd) btnAdd.style.display = 'none';
  }
}

async function doLogin(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value;
  const password = document.getElementById('loginPassword').value;
  const captcha_id = document.getElementById('loginCaptchaId')?.value;
  const captcha_answer = document.getElementById('loginCaptchaA')?.value;
  const res = await api('/api/login', 'POST', { email, password, captcha_id, captcha_answer });
  if (res.ok) {
    closeModal('loginModal');
    toast('Karibu, ' + res.name + '!');
    await checkAuth();
    if (res.must_change_password) {
      openModal('changePassModal');
      toast('Tafadhali badilisha nenosiri lako la mwanzo', true);
    }
  } else {
    toast(res.error || 'Login failed', true);
    loadCaptcha('login');
  }
}

async function doRegister(e) {
  e.preventDefault();
  const body = {
    name: document.getElementById('regName').value,
    email: document.getElementById('regEmail').value,
    phone: document.getElementById('regPhone').value,
    password: document.getElementById('regPassword').value,
    role: document.getElementById('regRole').value,
    captcha_id: document.getElementById('regCaptchaId')?.value,
    captcha_answer: document.getElementById('regCaptchaA')?.value
  };
  const res = await api('/api/register', 'POST', body);
  if (res.ok) {
    closeModal('registerModal');
    toast('Akaunti imeundwa! Karibu ' + res.name);
    await checkAuth();
  } else {
    toast(res.error || 'Registration failed', true);
    loadCaptcha('reg');
  }
}

async function logout() {
  await api('/api/logout', 'POST');
  currentUser = null;
  updateAuthUI();
  toast('Umetoka');
  showSection('home');
}

// ── LOCATION ─────────────────────────────────────
function detectLocation() {
  const label = document.getElementById('locLabel');
  if (!navigator.geolocation) {
    toast('Browser yako haiungi mkono location', true);
    return;
  }
  if (label) label.textContent = '...';
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      userLat = pos.coords.latitude;
      userLon = pos.coords.longitude;
      // Simple reverse: just show coords for now (can integrate Nominatim later)
      const locName = `${userLat.toFixed(3)}, ${userLon.toFixed(3)}`;
      if (label) label.textContent = locName.slice(0, 12);

      if (currentUser) {
        await api('/api/location', 'POST', {
          latitude: userLat,
          longitude: userLon,
          location: locName
        });
      }
      toast('Eneo limetambuliwa');
      // Refresh listings with distance
      if (document.getElementById('section-marketplace')?.classList.contains('active')) {
        loadListings();
      }
    },
    (err) => {
      if (label) label.textContent = 'Eneo';
      toast('Imeshindikana kupata eneo: ' + err.message, true);
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

// ── STATS ────────────────────────────────────────
async function loadStats() {
  const s = await api('/api/stats');
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v ?? '—'; };
  set('statUsers', s.users);
  set('statListings', s.listings);
  set('statMarkets', s.markets);
  set('statCountries', s.countries);
}

// ── LISTINGS ─────────────────────────────────────
async function loadListings() {
  const q = document.getElementById('listingSearch')?.value || '';
  const crop = document.getElementById('cropFilter')?.value || '';
  let url = `/api/listings?q=${encodeURIComponent(q)}&crop=${encodeURIComponent(crop)}`;
  if (userLat && userLon) url += `&lat=${userLat}&lon=${userLon}`;

  const items = await api(url);
  const grid = document.getElementById('listingsGrid');
  if (!grid) return;

  if (!items.length) {
    grid.innerHTML = '<p style="color:var(--text-muted);grid-column:1/-1">Hakuna listings zinazolingana.</p>';
    return;
  }

  grid.innerHTML = items.map(l => `
    <div class="card" onclick="openListing(${l.id})">
      <div class="card-header">
        <span class="card-title">${esc(l.crop)}</span>
        ${l.verified ? '<span class="card-badge">✓ Verified</span>' : ''}
      </div>
      <div class="card-price">${Number(l.price).toLocaleString()} TZS/kg</div>
      <div class="card-meta">
        📦 ${Number(l.quantity_kg).toLocaleString()} kg &nbsp;·&nbsp;
        📍 ${esc(l.location)}${l.country ? ', ' + esc(l.country) : ''}
        ${l.distance_km != null ? ` &nbsp;·&nbsp; 📏 ${l.distance_km} km` : ''}
      </div>
      <div class="card-meta" style="margin-top:0.4rem">
        👤 ${esc(l.seller_name || 'Seller')} ${l.seller_verified ? '✓' : ''}
      </div>
      <div class="card-actions" onclick="event.stopPropagation()">
        <button class="${l.liked ? 'active' : ''}" onclick="toggleLike(${l.id}, this)">
          ❤️ ${l.likes_count || 0}
        </button>
        <button onclick="openListing(${l.id})">
          💬 ${l.comments_count || 0}
        </button>
        <button onclick="openListing(${l.id})">View</button>
      </div>
    </div>
  `).join('');
}

async function openListing(id) {
  currentListingId = id;
  const data = await api(`/api/listings/${id}`);
  if (data.error) { toast(data.error, true); return; }

  const body = document.getElementById('detailBody');
  body.innerHTML = `
    <h2>${esc(data.crop)} ${data.verified ? '<span class="card-badge">✓ Verified</span>' : ''}</h2>
    <div class="card-price" style="margin:0.5rem 0">${Number(data.price).toLocaleString()} TZS/kg</div>
    <p class="card-meta">
      📦 ${Number(data.quantity_kg).toLocaleString()} kg &nbsp;·&nbsp;
      📍 ${esc(data.location)}, ${esc(data.country || '')}<br>
      👤 ${esc(data.seller_name || 'Seller')}
      ${data.seller_id ? ` · <button class="btn btn-ghost" style="padding:0.2rem 0.5rem;font-size:0.8rem" onclick="toggleFollow(${data.seller_id})">Follow</button>` : ''}<br>
      ❤️ ${data.likes_count || 0} likes · 💬 ${data.comments_count || 0} comments · 👁 ${data.views_count || 0} views
    </p>
    ${data.description ? `<p style="margin-top:1rem">${esc(data.description)}</p>` : ''}
    <div style="margin-top:1rem">
      <button class="btn ${data.liked ? 'btn-primary' : 'btn-outline'}" onclick="toggleLike(${id})">
        ${data.liked ? '❤️ Umeipenda' : '🤍 Penda'}
      </button>
    </div>
  `;

  document.getElementById('listingDetail').classList.remove('hidden');
  loadComments(id);
}

function closeDetail() {
  document.getElementById('listingDetail').classList.add('hidden');
  currentListingId = null;
}

async function toggleLike(id, btnEl) {
  if (!currentUser) { openModal('loginModal'); return; }
  const res = await api(`/api/listings/${id}/like`, 'POST');
  if (res.ok) {
    if (btnEl) {
      btnEl.classList.toggle('active', res.liked);
      btnEl.innerHTML = `❤️ ${res.likes_count}`;
    }
    // Refresh detail if open
    if (currentListingId === id) openListing(id);
  } else {
    toast(res.error || 'Error', true);
  }
}

async function toggleFollow(uid) {
  if (!currentUser) { openModal('loginModal'); return; }
  const res = await api(`/api/users/${uid}/follow`, 'POST');
  if (res.ok) {
    toast(res.following ? 'Umefuata!' : 'Umeacha kufuata');
  } else {
    toast(res.error || 'Error', true);
  }
}

// ── COMMENTS ─────────────────────────────────────
async function loadComments(lid) {
  const comments = await api(`/api/listings/${lid}/comments`);
  const list = document.getElementById('commentsList');
  if (!list) return;

  if (!comments.length) {
    list.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem">Hakuna maoni bado. Kuwa wa kwanza!</p>';
    return;
  }

  list.innerHTML = comments.map(c => `
    <div class="comment">
      <span class="comment-author">${esc(c.user_name)} ${c.user_verified ? '✓' : ''}</span>
      <span class="comment-time">${formatTime(c.created_at)}</span>
      <div class="comment-body">${esc(c.content)}</div>
    </div>
  `).join('');
}

async function postComment() {
  if (!currentUser) { openModal('loginModal'); return; }
  if (!currentListingId) return;

  const input = document.getElementById('commentInput');
  const content = input?.value?.trim();
  if (!content) return;

  const res = await api(`/api/listings/${currentListingId}/comments`, 'POST', { content });
  if (res.ok) {
    input.value = '';
    loadComments(currentListingId);
    toast('Maoni yametumwa');
  } else {
    toast(res.error || 'Error', true);
  }
}

// ── ADD LISTING ──────────────────────────────────
async function addListing(e) {
  e.preventDefault();
  if (!currentUser) { openModal('loginModal'); return; }

  const body = {
    crop: document.getElementById('listCrop').value,
    quantity_kg: document.getElementById('listQty').value,
    price: document.getElementById('listPrice').value,
    location: document.getElementById('listLocation').value,
    country: document.getElementById('listCountry').value,
    description: document.getElementById('listDesc').value,
    latitude: userLat,
    longitude: userLon
  };

  const res = await api('/api/listings', 'POST', body);
  if (res.ok) {
    closeModal('addListingModal');
    toast('Listing imewekwa!');
    loadListings();
  } else {
    toast(res.error || 'Error', true);
  }
}

// ── PRICES ───────────────────────────────────────
async function loadPrices() {
  const q = document.getElementById('priceSearch')?.value || '';
  const prices = await api(`/api/prices?q=${encodeURIComponent(q)}`);
  const tbody = document.querySelector('#pricesTable tbody');
  if (!tbody) return;

  tbody.innerHTML = prices.map(p => `
    <tr>
      <td><strong>${esc(p.crop)}</strong></td>
      <td>${esc(p.market)}</td>
      <td>${esc(p.country)}</td>
      <td>${Number(p.buy_price).toLocaleString()}</td>
      <td>${Number(p.sell_price).toLocaleString()}</td>
      <td>${Number(p.transport_per_kg).toLocaleString()}</td>
    </tr>
  `).join('');
}

// ── PROFIT INTELLIGENCE ──────────────────────────
async function runIntelligence() {
  const body = {
    crop: document.getElementById('intelCrop').value,
    quantity_kg: document.getElementById('intelQty').value,
    source_price: document.getElementById('intelBuy').value,
    extra_cost_per_kg: document.getElementById('intelExtra').value
  };
  const res = await api('/api/intelligence', 'POST', body);
  const el = document.getElementById('intelResults');
  if (!el) return;

  if (res.error) {
    el.innerHTML = `<p style="color:var(--danger)">${esc(res.error)}</p>`;
    return;
  }

  if (!res.results?.length) {
    el.innerHTML = '<p style="color:var(--text-muted)">Hakuna data ya bei kwa zao hili.</p>';
    return;
  }

  el.innerHTML = res.results.map((r, i) => `
    <div class="intel-card ${i === 0 ? 'best' : ''}">
      <div>
        <strong>${esc(r.market)}, ${esc(r.country)}</strong>
        ${i === 0 ? ' <span class="card-badge">BEST</span>' : ''}
        <div class="intel-meta">
          Sell: ${Number(r.sell_price).toLocaleString()} · Landed: ${Number(r.landed_cost).toLocaleString()} · Margin: ${r.margin_pct}%
        </div>
      </div>
      <div class="intel-profit">
        +${Number(r.profit_total).toLocaleString()} TZS
        <div class="intel-meta">${Number(r.profit_per_kg).toLocaleString()}/kg</div>
      </div>
    </div>
  `).join('');
}

// ── LIVE FEED ────────────────────────────────────
async function loadLive() {
  const items = await api('/api/live?limit=30');
  const feed = document.getElementById('liveFeed');
  if (!feed) return;

  if (!items.length) {
    feed.innerHTML = '<p style="color:var(--text-muted)">Hakuna shughuli bado. Anza kuingiliana na soko!</p>';
    return;
  }

  feed.innerHTML = items.map(a => `
    <div class="live-item">
      <span class="live-time">${formatTime(a.created_at)}</span>
      <span><strong>${esc(a.user_name || 'System')}</strong> — ${esc(a.message || a.action_type)}</span>
    </div>
  `).join('');
}

// ── AI CHAT ──────────────────────────────────────
async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input?.value?.trim();
  if (!msg) return;

  const box = document.getElementById('chatMessages');
  box.innerHTML += `<div class="chat-bubble user">${esc(msg)}</div>`;
  input.value = '';
  box.scrollTop = box.scrollHeight;

  const res = await api('/api/ai/chat', 'POST', { message: msg });
  const reply = res.reply || 'Samahani, sikuelewa. Jaribu tena.';
  box.innerHTML += `<div class="chat-bubble bot">${reply.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</div>`;
  box.scrollTop = box.scrollHeight;
}

// ── PRODUCT SLIDER ───────────────────────────────
const CROP_EMOJI = {
  'Mahindi': '🌽', 'Ufuta': '🌱', 'Maharage': '🫘',
  'Mpunga': '🌾', 'Korosho': '🥜', 'Kahawa': '☕', 'Chai': '🍵'
};
let sliderIndex = 0;
let sliderItems = [];

async function loadProductSlider() {
  const items = await api('/api/listings');
  sliderItems = Array.isArray(items) ? items.slice(0, 12) : [];
  const track = document.getElementById('productSlider');
  if (!track) return;

  if (!sliderItems.length) {
    track.innerHTML = '<p style="color:var(--text-muted);padding:1rem">Hakuna bidhaa bado.</p>';
    return;
  }

  track.innerHTML = sliderItems.map(l => `
    <div class="slider-card" onclick="openListing(${l.id})">
      <div class="crop-emoji">${CROP_EMOJI[l.crop] || '🌿'}</div>
      <h4>${esc(l.crop)}</h4>
      <div class="price">${Number(l.price).toLocaleString()} TZS/kg</div>
      <div class="meta">
        📦 ${Number(l.quantity_kg).toLocaleString()} kg<br>
        📍 ${esc(l.location)}
        ${l.verified ? ' · ✓' : ''}
      </div>
    </div>
  `).join('');

  sliderIndex = 0;
  updateSliderPosition();
}

function slideProducts(dir) {
  const track = document.getElementById('productSlider');
  if (!track || !sliderItems.length) return;
  const cardWidth = 276; // 260 + gap
  const visible = Math.max(1, Math.floor(track.parentElement.clientWidth / cardWidth));
  const maxIndex = Math.max(0, sliderItems.length - visible);
  sliderIndex = Math.max(0, Math.min(maxIndex, sliderIndex + dir));
  updateSliderPosition();
}

function updateSliderPosition() {
  const track = document.getElementById('productSlider');
  if (!track) return;
  const cardWidth = 276;
  track.style.transform = `translateX(-${sliderIndex * cardWidth}px)`;
}

// Auto-slide every 5 seconds
setInterval(() => {
  if (!document.getElementById('section-home')?.classList.contains('active')) return;
  if (!sliderItems.length) return;
  const track = document.getElementById('productSlider');
  if (!track) return;
  const cardWidth = 276;
  const visible = Math.max(1, Math.floor(track.parentElement.clientWidth / cardWidth));
  const maxIndex = Math.max(0, sliderItems.length - visible);
  sliderIndex = sliderIndex >= maxIndex ? 0 : sliderIndex + 1;
  updateSliderPosition();
}, 5000);

// ── AI MARKET MONITOR (every 60 seconds) ─────────
let aiMonitorTimer = null;

async function runAiMarketMonitor() {
  const el = document.getElementById('aiMarketMonitor');
  if (!el) return;

  // Fetch latest prices + listings
  const [prices, listings] = await Promise.all([
    api('/api/prices'),
    api('/api/listings')
  ]);

  const priceList = Array.isArray(prices) ? prices : [];
  const listingList = Array.isArray(listings) ? listings : [];

  // Pick top interesting items: mix of best prices and hot listings
  const cards = [];

  // Group prices by crop, pick lowest sell per crop as "best buy market"
  const byCrop = {};
  priceList.forEach(p => {
    if (!byCrop[p.crop] || p.sell_price < byCrop[p.crop].sell_price) {
      byCrop[p.crop] = p;
    }
  });

  Object.values(byCrop).slice(0, 4).forEach(p => {
    cards.push({
      tag: 'Best Price',
      title: p.crop,
      val: Number(p.sell_price).toLocaleString() + ' TZS',
      sub: `${p.market}, ${p.country} · Buy ${Number(p.buy_price).toLocaleString()}`,
      highlight: true
    });
  });

  // Hot listings (most likes or newest)
  const hot = [...listingList]
    .sort((a, b) => (b.likes_count || 0) - (a.likes_count || 0))
    .slice(0, 4);

  hot.forEach(l => {
    cards.push({
      tag: 'Hot Listing',
      title: l.crop,
      val: Number(l.price).toLocaleString() + ' TZS/kg',
      sub: `${Number(l.quantity_kg).toLocaleString()} kg · ${l.location} · ❤️ ${l.likes_count || 0}`,
      highlight: false,
      id: l.id
    });
  });

  if (!cards.length) {
    el.innerHTML = '<div class="monitor-loading">Hakuna data ya soko bado.</div>';
    return;
  }

  const now = new Date().toLocaleTimeString('sw-TZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  el.innerHTML = cards.map(c => `
    <div class="monitor-card ${c.highlight ? 'highlight' : ''}" ${c.id ? `onclick="openListing(${c.id})" style="cursor:pointer"` : ''}>
      <div class="tag">${c.tag}</div>
      <h4>${esc(c.title)}</h4>
      <div class="val">${c.val}</div>
      <div class="sub">${esc(c.sub)}</div>
    </div>
  `).join('') + `<div class="monitor-updated" style="grid-column:1/-1">🔄 AI updated · ${now}</div>`;

  // Update badge
  const badge = document.getElementById('aiMonitorBadge');
  if (badge) badge.textContent = `● Live · last update ${now}`;
}

function startAiMarketMonitor() {
  runAiMarketMonitor();
  if (aiMonitorTimer) clearInterval(aiMonitorTimer);
  aiMonitorTimer = setInterval(runAiMarketMonitor, 60000); // every 60 seconds
}

// ── WELCOME MESSAGE (bilingual) ──────────────────
const WELCOME_MSG = `
  <div class="chat-bubble bot">
    <strong>🇬🇧 WELCOME TO NJIAMAUZO AFRIKA</strong><br>
    <em>THE HUB OF BUSINESS · I AM READY TO SERVE YOU. THANK YOU.</em>
    <br><br>
    <strong>🇹🇿 KARIBU NJIAMAUZO AFRIKA</strong><br>
    <em>KITOVU CHA BIASHARA · NIKO TAYARI KUKUHUDUMIA. ASANTE.</em>
    <br><br>
    🌾 Ninaweza kukusaidia kutafuta mazao, bei za soko, na soko lenye faida. Andika swali lako!
  </div>
`;


// ── CAPTCHA ──────────────────────────────────────
async function loadCaptcha(prefix) {
  const res = await api('/api/captcha');
  if (!res.captcha_id) return;
  const qEl = document.getElementById(prefix + 'CaptchaQ');
  const idEl = document.getElementById(prefix + 'CaptchaId');
  if (qEl) qEl.textContent = res.question;
  if (idEl) idEl.value = res.captcha_id;
}

// Override openModal to load captcha
const _openModal = openModal;
openModal = function(id) {
  _openModal(id);
  if (id === 'loginModal') loadCaptcha('login');
  if (id === 'registerModal') loadCaptcha('reg');
};

// ── FORGOT PASSWORD + OTP ────────────────────────
let forgotResetToken = null;
let forgotEmail = '';
let forgotPhone = '';

async function sendForgotOtp() {
  const contact = document.getElementById('forgotContact').value.trim();
  const channel = document.getElementById('forgotChannel').value;
  if (!contact) { toast('Weka email au simu', true); return; }

  const body = { purpose: 'RESET', channel };
  if (channel === 'EMAIL' || contact.includes('@')) {
    body.email = contact;
    forgotEmail = contact;
  } else {
    body.phone = contact;
    forgotPhone = contact;
  }

  const res = await api('/api/otp/send', 'POST', body);
  if (res.ok) {
    document.getElementById('forgotStep1').classList.add('hidden');
    document.getElementById('forgotStep2').classList.remove('hidden');
    const hint = document.getElementById('forgotDemoHint');
    if (hint && res.demo_code) {
      hint.textContent = 'DEMO OTP: ' + res.demo_code + ' (production itatumwa kweli)';
    }
    toast('OTP imetumwa kupitia ' + channel);
  } else {
    toast(res.error || 'Imeshindikana', true);
  }
}

async function verifyForgotOtp() {
  const code = document.getElementById('forgotOtp').value.trim();
  const body = { code, purpose: 'RESET' };
  if (forgotEmail) body.email = forgotEmail;
  if (forgotPhone) body.phone = forgotPhone;

  const res = await api('/api/otp/verify', 'POST', body);
  if (res.ok) {
    forgotResetToken = res.reset_token;
    document.getElementById('forgotStep2').classList.add('hidden');
    document.getElementById('forgotStep3').classList.remove('hidden');
    toast('OTP imethibitishwa');
  } else {
    toast(res.error || 'OTP si sahihi', true);
  }
}

async function resetPassword() {
  const new_password = document.getElementById('forgotNewPass').value;
  const res = await api('/api/password/reset', 'POST', {
    new_password,
    reset_token: forgotResetToken
  });
  if (res.ok) {
    closeModal('forgotModal');
    toast('Nenosiri limebadilishwa! Ingia sasa.');
    openModal('loginModal');
    // reset steps
    document.getElementById('forgotStep1').classList.remove('hidden');
    document.getElementById('forgotStep2').classList.add('hidden');
    document.getElementById('forgotStep3').classList.add('hidden');
  } else {
    toast(res.error || 'Imeshindikana', true);
  }
}

async function doChangePassword() {
  const current_password = document.getElementById('changeCurrent').value;
  const new_password = document.getElementById('changeNew').value;
  const res = await api('/api/password/change', 'POST', { current_password, new_password });
  if (res.ok) {
    closeModal('changePassModal');
    toast('Nenosiri limebadilishwa!');
  } else {
    toast(res.error || 'Imeshindikana', true);
  }
}

// ── ONLINE PAYMENTS ──────────────────────────────
async function initiatePayment() {
  const amount = document.getElementById('payAmount').value;
  const method = document.getElementById('payMethod').value;
  const phone = document.getElementById('payPhone').value;
  const res = await api('/api/payments/initiate', 'POST', {
    amount, method, phone, purpose: 'SERVICE', country: 'Tanzania'
  });
  const box = document.getElementById('payResult');
  if (!box) return;
  box.classList.remove('hidden');

  if (res.ok) {
    let html = `<strong>Reference:</strong> ${esc(res.reference)}<br>
      <strong>Status:</strong> ${esc(res.status)}<br>
      ${esc(res.instructions || '')}`;
    if (res.require_otp && res.demo_otp) {
      html += `<br><br><strong>DEMO OTP:</strong> ${res.demo_otp}
        <div class="form-group" style="margin-top:0.5rem">
          <input type="text" id="payOtp" placeholder="Weka OTP" />
          <button class="btn btn-primary" style="margin-top:0.4rem" onclick="confirmPayment('${res.reference}')">Thibitisha Malipo</button>
        </div>`;
    } else {
      html += `<br><button class="btn btn-primary" style="margin-top:0.5rem" onclick="confirmPayment('${res.reference}')">Simulia Uthibitisho (Demo)</button>`;
    }
    box.innerHTML = html;
    toast('Malipo yameanzishwa');
  } else {
    box.innerHTML = `<span style="color:var(--danger)">${esc(res.error || 'Error')}</span>`;
    toast(res.error || 'Error', true);
  }
}

async function confirmPayment(ref) {
  const otp = document.getElementById('payOtp')?.value || '';
  const res = await api('/api/payments/confirm', 'POST', { reference: ref, otp });
  if (res.ok) {
    toast('✅ Malipo yamethibitishwa!');
    const box = document.getElementById('payResult');
    if (box) box.innerHTML = `<strong style="color:var(--success)">✅ VERIFIED</strong> — ${esc(res.reference)}`;
  } else {
    toast(res.error || 'Imeshindikana', true);
  }
}

// ── INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Only run full init on main page (not admin)
  if (!document.getElementById('section-home')) return;

  await checkAuth();
  loadStats();
  loadProductSlider();
  startAiMarketMonitor();

  // Bilingual welcome message in chat
  const chatBox = document.getElementById('chatMessages');
  if (chatBox) {
    chatBox.innerHTML = WELCOME_MSG;
  }

  // Auto-refresh live every 30s if visible
  setInterval(() => {
    if (document.getElementById('section-live')?.classList.contains('active')) {
      loadLive();
    }
  }, 30000);

  // Refresh slider when returning to home
  const origShow = showSection;
  window.showSection = function(name) {
    origShow(name);
    if (name === 'home') {
      loadProductSlider();
      runAiMarketMonitor();
    }
  };
});
