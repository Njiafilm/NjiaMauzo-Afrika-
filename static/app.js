async function api(u,o={}){let r=await fetch(u,{headers:{'Content-Type':'application/json'},...o}),d=await r.json();if(!r.ok)throw Error(d.error||'Error');return d}
function show(id){document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));document.getElementById(id).classList.add('active');if(id==='prices')loadPrices();if(id==='market')loadListings();if(id==='account')loadAccount()}
function money(n){return 'TZS '+Number(n).toLocaleString(undefined,{maximumFractionDigits:0})}
async function loadStats(){let d=await api('/api/stats');stats.innerHTML=Object.entries({Watumiaji:d.users,'Bidhaa':d.listings,'Masoko':d.markets,'Nchi':d.countries}).map(([k,v])=>`<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('')}
async function loadPrices(){let q=pq?.value||'',c=pc?.value||'',d=await api('/api/prices?q='+encodeURIComponent(q)+'&country='+encodeURIComponent(c));ptable.innerHTML=d.map(x=>`<tr><td><b>${x.crop}</b></td><td>${x.market}</td><td>${x.country}</td><td>${money(x.buy_price)}/kg</td><td>${money(x.sell_price)}/kg</td><td>${money(x.transport_per_kg)}</td><td>${new Date(x.recorded_at).toLocaleDateString()}</td></tr>`).join('');if(!q&&!c)homePrices.innerHTML=d.slice(0,6).map(x=>`<div class="price"><b>🌾 ${x.crop}</b><p>📍 ${x.market}, ${x.country}</p><strong>${money(x.sell_price)}/kg</strong></div>`).join('')}
async function analyze(){try{let d=await api('/api/intelligence',{method:'POST',body:JSON.stringify({crop:icrop.value,quantity_kg:iqty.value,source_price:ibuy.value,extra_cost_per_kg:iextra.value})});let r=d.recommendation;recommend.innerHTML=r?`<div class="good"><h3>🏆 Soko Bora: ${r.market}, ${r.country}</h3><b>Makadirio ya faida: ${money(r.profit_total)}</b><p>${money(r.profit_per_kg)}/kg • Margin ${r.margin_pct.toFixed(1)}%</p><small>⚠️ Demo estimate; thibitisha bei, ubora, kodi na usafiri kabla ya biashara.</small></div>`:'';intelTable.innerHTML=d.results.map(x=>`<tr><td><b>${x.market}</b><br>${x.country}</td><td>${money(x.sell_price)}</td><td>${money(x.transport)}</td><td>${money(x.landed_cost)}</td><td>${money(x.profit_per_kg)}</td><td><b>${money(x.profit_total)}</b></td><td>${x.margin_pct.toFixed(1)}%</td></tr>`).join('')}catch(e){alert(e.message)}}
async function aiSearch(){try{let d=await api('/api/ai/search',{method:'POST',body:JSON.stringify({query:aiq.value})});let i=d.interpreted;interpret.innerHTML=`<div class="card"><b>AI imeelewa:</b> ${i.crop||'zao lolote'} • ${i.location||'eneo lolote'} • ${i.quantity_kg?Number(i.quantity_kg).toLocaleString()+' kg':'kiasi chochote'} • ${i.max_price?money(i.max_price)+'/kg max':'bei yoyote'}</div>`;results.innerHTML=d.results.map(x=>`<div class="card"><h3>🌾 ${x.crop} ${x.verified?'✅':''}</h3><p>📦 ${(x.quantity_kg/1000).toLocaleString()} tani<br>📍 ${x.location}, ${x.country}</p><b>${money(x.price)}/kg</b><p>Match: ${x.match_score}</p></div>`).join('')||'<div class="card">Hakuna bidhaa inayolingana.</div>'}catch(e){alert(e.message)}}
async function chatSend(){let q=chatq.value.trim();if(!q)return;chatq.value='';chat.innerHTML+=`<div class="msg"><b>Wewe:</b> ${q}</div>`;let d=await api('/api/ai/chat',{method:'POST',body:JSON.stringify({message:q})});chat.innerHTML+=`<div class="msg"><b>AI:</b> ${d.reply}</div>`}
async function loadListings(){let q=lq?.value||'',d=await api('/api/listings?q='+encodeURIComponent(q));listings.innerHTML=d.map(x=>`<div class="card"><h3>🌾 ${x.crop} ${x.verified?'✅':''}</h3><p>📦 ${(x.quantity_kg/1000).toLocaleString()} tani<br>📍 ${x.location}, ${x.country}</p><b>${money(x.price)}/kg</b></div>`).join('')||'<div class="card">Hakuna bidhaa.</div>'}
function openModal(html){modalBody.innerHTML=html;modal.classList.add('open')}function closeModal(){modal.classList.remove('open')}
function loginBox(){openModal(`<h2>🔐 Ingia</h2><input id="le" placeholder="Email"><input id="lp" type="password" placeholder="Password"><button onclick="login()">Ingia</button><p>Huna akaunti? <a href="#" onclick="registerBox()">Jisajili</a></p>`)}
function registerBox(){openModal(`<h2>📝 Jisajili</h2><input id="rn" placeholder="Jina"><input id="re" placeholder="Email"><input id="rp" type="password" placeholder="Password"><input id="rph" placeholder="Simu"><select id="rr"><option value="buyer">Mnunuzi</option><option value="seller">Mkulima/Muuzaji</option></select><button onclick="register()">Jisajili</button>`)}
async function login(){try{let d=await api('/api/login',{method:'POST',body:JSON.stringify({email:le.value,password:lp.value})});closeModal();loadAccount();alert('Karibu '+d.name)}catch(e){alert(e.message)}}
async function register(){try{let d=await api('/api/register',{method:'POST',body:JSON.stringify({name:rn.value,email:re.value,password:rp.value,phone:rph.value,role:rr.value})});closeModal();loadAccount();alert('Akaunti imeundwa')}catch(e){alert(e.message)}}
async function loadAccount(){let d=await api('/api/me');accountBox.innerHTML=d.logged_in?`<h3>Karibu ${d.name}</h3><p>Role: ${d.role}</p><button onclick="logout()">Toka</button>`:`<button onclick="loginBox()">Ingia</button> <button onclick="registerBox()">Jisajili</button>`}
async function logout(){await api('/api/logout',{method:'POST'});loadAccount()}
async function createAlert(){try{await api('/api/alerts',{method:'POST',body:JSON.stringify({crop:alertCrop.value,target_price:alertPrice.value,direction:'ABOVE'})});alert('Price Alert imehifadhiwa')}catch(e){alert(e.message)}}
async function pay(){try{let d=await api('/api/payment',{method:'POST',body:JSON.stringify({amount:10000,method:'MOBILE_MONEY'})});alert('Payment reference: '+d.reference)}catch(e){alert(e.message)}}
function openListing(){openModal(`<h2>💰 Weka Zao</h2><input id="lc" placeholder="Zao"><input id="lq2" type="number" placeholder="Kiasi kg"><input id="lprice" type="number" placeholder="Bei/kg"><input id="lloc" placeholder="Eneo"><button onclick="createListing()">Chapisha</button>`)}
async function createListing(){try{await api('/api/listings',{method:'POST',body:JSON.stringify({crop:lc.value,quantity_kg:lq2.value,price:lprice.value,location:lloc.value,country:'Tanzania'})});closeModal();loadListings()}catch(e){alert(e.message)}}
loadStats();loadPrices();loadListings();loadAccount();
async function updateServiceFee(){try{let d=await api('/api/service/fee?country='+encodeURIComponent(serviceCountry.value));serviceFee.innerHTML=`<div class="good"><b>Ada: TZS ${Number(d.base_amount_tzs).toLocaleString()}</b> ≈ <b>${Number(d.amount).toLocaleString()} ${d.currency}</b><br><small>${d.note}</small></div>`}catch(e){}}
async function startService(){
  try{
    let q=serviceq.value.trim(); if(!q) return alert('Andika kwanza bidhaa/zao unalotafuta.');
    let s=await api('/api/service/start',{method:'POST',body:JSON.stringify({query:q})});
    let f=await api('/api/service/fee?country='+encodeURIComponent(serviceCountry.value));
    openModal(`<h2>💳 Lipa ili kusaidiwa</h2><p>Ombi: <b>${q}</b></p><div class="good"><b>${Number(f.amount).toLocaleString()} ${f.currency}</b> — sawa na TZS 1,000</div><input id="sp" value="${servicePhone.value||''}" placeholder="Namba ya simu ya malipo"><button onclick="payService(${s.request_id},'${f.currency}')">Lipa sasa</button><small>Baada ya gateway kuthibitisha malipo, User Room itafunguliwa moja kwa moja.</small>`);
  }catch(e){alert(e.message)}
}
async function payService(rid,currency){
  try{
    let d=await api('/api/service/pay',{method:'POST',body:JSON.stringify({request_id:rid,country:serviceCountry.value,phone:sp.value,currency})});
    closeModal();
    serviceq.value='';
    show('service');
    serviceRoom.innerHTML=`<div class="card"><h3>⏳ Malipo yanasubiri uthibitisho</h3><p>Reference: <b>${d.reference}</b></p><p>Mfumo unakagua gateway moja kwa moja. User Room itafunguka baada ya verification.</p><button onclick="checkService(${rid})">🔄 Kagua sasa</button></div>`;
    window.nmPaymentWatch=setInterval(async()=>{try{let s=await api('/api/service/status/'+rid);if(s.status==='VERIFIED'){clearInterval(window.nmPaymentWatch);let room=await api('/api/service/room',{method:'POST',body:JSON.stringify({request_id:rid})});renderServiceRoom(room);}}catch(e){}},5000);
  }catch(e){alert(e.message)}
}
async function checkService(rid){
  try{
    let d=await api('/api/service/status/'+rid);
    if(d.status==='VERIFIED'){let room=await api('/api/service/room',{method:'POST',body:JSON.stringify({request_id:rid})});renderServiceRoom(room);}
    else {serviceRoom.innerHTML=`<div class="card"><h3>⏳ Bado haijathibitishwa</h3><p>Subiri uthibitisho wa gateway.</p><button onclick="checkService(${rid})">🔄 Kagua tena</button></div>`}
  }catch(e){alert(e.message)}
}
function renderServiceRoom(d){
  serviceRoom.innerHTML=`<div class="good"><h2>🔓 USER ROOM — Imefunguliwa</h2><p>${d.message}</p></div>
  <div class="card"><h3>🔎 Mfumo umeelewa</h3><p>${d.interpreted.crop||'Bidhaa yoyote'} • ${d.interpreted.location||'Soko lolote'} • ${d.interpreted.quantity_kg?Number(d.interpreted.quantity_kg).toLocaleString()+' kg':'kiasi chochote'}</p></div>
  <h3>🌾 Bidhaa zilizopatikana</h3><div class="grid">${d.products.map(x=>`<div class="card"><h3>🌾 ${x.crop} ${x.verified?'✅':''}</h3><p>📦 ${(x.quantity_kg/1000).toLocaleString()} tani<br>📍 ${x.location}, ${x.country}</p><b>${money(x.price)}/kg</b><p>Match: ${x.match_score}</p></div>`).join('')||'<div class="card">Bado hakuna listing inayolingana.</div>'}</div>
  <h3>🌍 Masoko yaliyopatikana</h3><div class="grid">${d.markets.map(x=>`<div class="card"><h3>${x.market}</h3><p>${x.country} • ${x.crop}</p><b>${money(x.sell_price)}/kg</b><p>Usafiri: ${money(x.transport_per_kg)}/kg</p></div>`).join('')||'<div class="card">Hakuna market match.</div>'}</div>`;
}
serviceCountry?.addEventListener('change',updateServiceFee);
async function maybeOffer(){
  if(sessionStorage.getItem('nm_service_offer_seen')) return;
  sessionStorage.setItem('nm_service_offer_seen','1');
  openModal(`<h2>🤝 Unahitaji msaada?</h2><p>Unaweza kutazama bidhaa mwenyewe bure, au NjiaMauzo Afrika ikusaidie <b>kutafuta bidhaa na masoko kulingana na ombi lako</b>.</p><p>Ada ya huduma ni <b>TZS 1,000</b> au thamani yake katika fedha ya nchi yako.</p><button onclick="closeModal();show('service');updateServiceFee()">Ndiyo, nisaidie kutafuta</button><button class="secondary" onclick="closeModal()">Hapana, nitaangalia mwenyewe</button>`);
}
setTimeout(maybeOffer,800);
