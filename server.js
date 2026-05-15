const express = require('express');
const path = require('path');
const fs = require('fs');
const https = require('https');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({limit:'10mb'}));

// ── Telegram ────────────────────────────────────────────────────────────────
const TG_TOKEN = process.env.TELEGRAM_TOKEN || process.env.TELEGRAM_BOT_TOKEN;
const TG_CHAT  = process.env.TELEGRAM_CHAT_ID;

function sendTelegram(msg){
  if(!TG_TOKEN||!TG_CHAT)return;
  const body=JSON.stringify({chat_id:TG_CHAT,text:msg,parse_mode:'HTML'});
  const req=https.request({
    hostname:'api.telegram.org',
    path:`/bot${TG_TOKEN}/sendMessage`,
    method:'POST',
    headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}
  });
  req.on('error',e=>console.error('TG:',e.message));
  req.write(body);req.end();
}

// ── Data store (JSON file) ───────────────────────────────────────────────────
const DATA_FILE = process.env.DATA_PATH || path.join('/app/data', 'data.json');

function loadData(){
  try{ return JSON.parse(fs.readFileSync(DATA_FILE,'utf8')); }
  catch(e){ return {users:{}}; }
}

function saveData(data){
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// ── Auth endpoints ───────────────────────────────────────────────────────────

// Kayıt / İlk giriş
app.post('/auth/register', (req, res) => {
  const {name, pin, visits} = req.body||{};
  if(!name||!pin) return res.json({ok:false, error:'Eksik bilgi'});
  if(!/^\d{4}$/.test(pin)) return res.json({ok:false, error:'PIN 4 haneli olmalı'});

  const data = loadData();
  const key = name.trim().toLowerCase().replace(/\s+/g,'_');

  if(data.users[key]){
    return res.json({ok:false, error:'Bu isim zaten kayıtlı. Giriş yapın.'});
  }

  data.users[key] = {
    name: name.trim(),
    pin,
    visits: visits||[],
    createdAt: new Date().toISOString()
  };
  saveData(data);

  const now = new Date().toLocaleString('tr-TR',{timeZone:'Europe/Istanbul'});
  sendTelegram(`👤 <b>Yeni Kullanıcı</b>\n\nİsim: <b>${name}</b>\nZaman: ${now}`);

  res.json({ok:true, name:name.trim(), visits:data.users[key].visits});
});

// Giriş
app.post('/auth/login', (req, res) => {
  const {name, pin} = req.body||{};
  if(!name||!pin) return res.json({ok:false, error:'Eksik bilgi'});

  const data = loadData();
  const key = name.trim().toLowerCase().replace(/\s+/g,'_');
  const user = data.users[key];

  if(!user) return res.json({ok:false, error:'Kullanıcı bulunamadı. Kayıt olun.'});
  if(user.pin !== pin) return res.json({ok:false, error:'PIN hatalı.'});

  const now = new Date().toLocaleString('tr-TR',{timeZone:'Europe/Istanbul'});
  sendTelegram(`🔑 <b>Giriş</b>\n\nİsim: <b>${name}</b>\nZaman: ${now}`);

  const sortedVisits = (user.visits||[]).slice().sort((a,b)=>(b.id||0)-(a.id||0));
  res.json({ok:true, name:user.name, visits:sortedVisits});
});

// Ziyaret kaydet
app.post('/visits/save', (req, res) => {
  const {name, pin, visit} = req.body||{};
  if(!name||!pin||!visit) return res.json({ok:false, error:'Eksik bilgi'});

  const data = loadData();
  const key = name.trim().toLowerCase().replace(/\s+/g,'_');
  const user = data.users[key];

  if(!user||user.pin!==pin) return res.json({ok:false, error:'Yetkisiz'});

  if(!user.visits) user.visits=[];
  // Var olan ziyareti güncelle (id eşleşmesi)
  const existIdx = user.visits.findIndex(v => v.id === visit.id);
  if(existIdx >= 0){
    user.visits[existIdx] = visit; // güncelle
  } else {
    user.visits.unshift(visit); // yeni ekle
  }
  if(user.visits.length>100) user.visits.splice(100);
  saveData(data);

  const now = new Date().toLocaleString('tr-TR',{timeZone:'Europe/Istanbul'});
  sendTelegram(`💾 <b>Ziyaret Kaydedildi</b>\n\nKullanıcı: <b>${user.name}</b>\nMağaza: ${visit.store||'-'}\nReyon: ${visit.reyon||'-'}\nZaman: ${now}`);

  res.json({ok:true, visits:user.visits});
});

// Ziyaret sil
app.post('/visits/delete', (req, res) => {
  const {name, pin, visitId} = req.body||{};
  if(!name||!pin||!visitId) return res.json({ok:false});

  const data = loadData();
  const key = name.trim().toLowerCase().replace(/\s+/g,'_');
  const user = data.users[key];
  if(!user||user.pin!==pin) return res.json({ok:false, error:'Yetkisiz'});

  user.visits=(user.visits||[]).filter(v=>v.id!==visitId);
  saveData(data);
  res.json({ok:true, visits:user.visits});
});

// Mail bildirimi
app.post('/notify-user', (req, res) => {
  const {name, action, store, reyon, week} = req.body||{};
  if(!name) return res.json({ok:false});
  const now = new Date().toLocaleString('tr-TR',{timeZone:'Europe/Istanbul'});
  if(action==='mail'){
    sendTelegram(`📧 <b>Mail Gönderildi</b>\n\nKullanıcı: <b>${name}</b>\nMağaza: ${store||'-'}\nReyon: ${reyon||'-'}\nHafta: ${week||'-'}\nZaman: ${now}`);
  }
  res.json({ok:true});
});



// ── AI Analiz endpoint ──────────────────────────────────────────────────────
app.post('/ai/analyze', async (req, res) => {
  const {mag, feedbacks, kwResults} = req.body||{};
  if(!mag||!feedbacks) return res.json({ok:false, error:'Eksik bilgi'});

  const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;
  if(!ANTHROPIC_KEY) return res.json({ok:false, error:'API key yok'});

  // MAG veri yapısı
  const erkekMAG = {
    "BUC":{bg:["CHINO DUVARI","DIŞ GİYİM","DOKUMA ÜST","ÖRME","ÖRME BASIC","TRİKO"],kl:{"CHINO DUVARI":["BASİC DOKUMA CHİNO PANTOLON İNCE","BASIC DOKUMA CHINO PANTOLON ORTA","CL BASIC DOKUMA PANTOLON KALIN","CLASSIC DOKUMA ROLLER","CLASSIC DOKUMA ŞORT"],"DIŞ GİYİM":["İNCE MONT","İNCE PUFFER MONT","MONT/KABAN KALIN","PARKA","PU MONT İNCE","PU MONT KALIN","YELEK"],"DOKUMA ÜST":["KEY DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK U.KOL","KEY EKOSELİ DOKUMA GOMLEK K.KOL","KEY EKOSELİ DOKUMA GOMLEK U.KOL"],"ÖRME":["BASIC ORME BİSİKLET YAKA T-SHIRT K.KOL","BASIC ORME POLO YAKA T-SHIRT K.KOL","BASIC ORME V YAKA T-SHIRT K.KOL","KEY BASKILI ORME T-SHIRT K.KOL","KEY ORME T-SHIRT K.KOL"],"ÖRME BASIC":["BASIC KEY BASKILI ORME SWEAT","CL BASIC ORME HIRKA","CL BASIC ORME PANTOLON","CL BASIC ORME ROLLER","CL BASIC ORME SORT / BERMUDA","CL BASIC ORME SWEAT","CL BASIC ORME T-SHIRT U.KOL","ÖRME ATLET"],"TRİKO":["KEY ÇİZGİLİ TRIKO KAZAK","KEY TRIKO HIRKA","KEY TRIKO HIRKA MONT","KEY TRIKO KAZAK","KEY TRIKO YELEK"]}},
    "BUB":{bg:["BLAZER CEKET","DENİM","DIŞ GİYİM","DOKUMA ALT","DOKUMA SET","DOKUMA ÜST","ÖRME","TRİKO"],kl:{"BLAZER CEKET":["BLAZER CEKET"],"DENİM":["KEY DOKUMA JEAN PANTOLON"],"DIŞ GİYİM":["İNCE MONT","MONT/KABAN KALIN","NAYLON PUFFER MONT/KABAN","PARKA","PU MONT İNCE","PU MONT KALIN","YAGMURLUK","YELEK"],"DOKUMA ALT":["KEY DOKUMA PANTOLON ORTA","KEY DOKUMA ŞORT/BERMUDA"],"DOKUMA SET":["BLAZER CEKET SET","DOKUMA SHACKET SET","İNCE MONT SET"],"DOKUMA ÜST":["DOKUMA SHACKET","KEY BASKILI DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK U.KOL"],"ÖRME":["KEY BASKILI ORME T-SHIRT K.KOL","KEY ORME HIRKA","KEY ORME PANTOLON","KEY ORME SORT / BERMUDA","KEY ORME SWEAT","KEY ORME T-SHIRT K.KOL"],"TRİKO":["KEY TRIKO HIRKA","KEY TRIKO KAZAK","KEY TRIKO KAZAK K.KOL","KEY TRIKO SUVETER","KEY TRIKO YELEK"]}},
    "BUL":{bg:["BLAZER CEKET","DIŞ GİYİM","DOKUMA ALT","DOKUMA ÜST","ÖRME","TRİKO"],kl:{"BLAZER CEKET":["BLAZER CEKET"],"DIŞ GİYİM":["İNCE MONT","MONT/KABAN KALIN","NAYLON PUFFER MONT/KABAN","PARKA","PU MONT İNCE","PU MONT KALIN","YAGMURLUK","YELEK"],"DOKUMA ALT":["KEY DOKUMA PANTOLON ORTA","KEY DOKUMA ŞORT/BERMUDA"],"DOKUMA ÜST":["DOKUMA SHACKET","KEY BASKILI DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK U.KOL"],"ÖRME":["KEY BASKILI ORME T-SHIRT K.KOL","KEY ÇİZGİLİ ORME T-SHIRT K.KOL","KEY ÖRME ATLET","KEY ORME HIRKA","KEY ORME PANTOLON","KEY ORME SORT / BERMUDA","KEY ORME SWEAT","KEY ORME T-SHIRT K.KOL"],"TRİKO":["KEY TRIKO HIRKA","KEY TRIKO HIRKA MONT","KEY TRIKO KAZAK","KEY TRIKO KAZAK K.KOL","KEY TRIKO SUVETER"]}},
    "BUXL":{bg:["DENİM","DIŞ GİYİM","DOKUMA ALT","DOKUMA ÜST","ÖRME","TRİKO"],kl:{"DENİM":["KEY DOKUMA JEAN BERMUDA","KEY DOKUMA JEAN GOMLEK K.KOL","KEY DOKUMA JEAN GOMLEK U.KOL","KEY DOKUMA JEAN MONT","KEY DOKUMA JEAN PANTOLON"],"DIŞ GİYİM":["İNCE MONT","İNCE PUFFER MONT","MONT/KABAN KALIN","NAYLON PUFFER MONT/KABAN","PARKA","PU MONT İNCE","PU MONT KALIN","YAGMURLUK","YELEK"],"DOKUMA ALT":["KEY DOKUMA PANTOLON KARGO","KEY DOKUMA PANTOLON ORTA","KEY DOKUMA ŞORT/BERMUDA"],"DOKUMA ÜST":["DOKUMA SHACKET","KEY DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK U.KOL"],"ÖRME":["BASIC ORME T-SHIRT K.KOL","KEY BASKILI ORME T-SHIRT K.KOL","KEY ÖRME ATLET","KEY ORME HIRKA","KEY ORME PANTOLON","KEY ORME POLO YAKA T-SHIRT K.KOL","KEY ORME SORT / BERMUDA","KEY ORME SWEAT"],"TRİKO":["KEY ÇİZGİLİ TRIKO KAZAK","KEY TRIKO HIRKA","KEY TRIKO KAZAK","KEY TRIKO KAZAK K.KOL","KEY TRIKO KAZAK Z4"]}},
    "BUMH":{bg:["DOKUMA ÜST","ÖRME","YÜZME GİYİM"],kl:{"DOKUMA ÜST":["KEY DOKUMA GOMLEK K.KOL"],"ÖRME":["BASIC ORME POLO YAKA T-SHIRT K.KOL","KEY ÖRME ATLET","KEY ORME T-SHIRT K.KOL"],"YÜZME GİYİM":["BASIC DOKUMA YUZME ŞORT","DOKUMA YUZME UZUN ŞORT","KEY DOKUMA YUZME ŞORT"]}},
    "BUCF":{bg:["BLAZER CEKET","DOKUMA ALT","DOKUMA ÜST","KRAVAT/PAPYON"],kl:{"BLAZER CEKET":["BLAZER CEKET"],"DOKUMA ALT":["KEY DOKUMA PANTOLON"],"DOKUMA ÜST":["BASIC DOKUMA GOMLEK U.KOL","KEY DOKUMA GOMLEK K.KOL","KEY DOKUMA GOMLEK U.KOL"],"KRAVAT/PAPYON":["KEY AKSESUAR KRAVAT/PAPYON SMART"]}},
    "BUGA":{bg:["AKTİF SPOR","DIŞ GİYİM","DOKUMA ALT"],kl:{"AKTİF SPOR":["BASIC ORME T-SHIRT K.KOL AKTİF SPOR","KEY ORME ATLET AKTİF SPOR","KEY ORME HIRKA AKTİF SPOR","KEY ORME PANTOLON AKTİF SPOR","KEY ORME SORT/TAYTLI SORT AKTİF SPOR","KEY ORME SWEAT AKTİF SPOR","KEY ORME T-SHIRT U.KOL AKTİF SPOR"],"DIŞ GİYİM":["MONT/KABAN KALIN"],"DOKUMA ALT":["KEY DOKUMA PANTOLON"]}},
    "BUJD":{bg:["DENİM"],kl:{"DENİM":["BASIC DOKUMA JEAN BERMUDA","BASIC DOKUMA JEAN PANTOLON"]}},
    "BUJW":{bg:["DENİM","DENIM DUVARI"],kl:{"DENİM":["KEY DOKUMA JEAN GOMLEK K.KOL","KEY DOKUMA JEAN GOMLEK U.KOL","KEY DOKUMA JEAN MONT"],"DENIM DUVARI":["BASIC DENIM DUVAR DOKUMA JEAN PANTOLON","BASIC DENIM DUVAR DOKUMA JEAN SORT /BERMUDA"]}},
    "BUK":{bg:["DERİ AKSESUAR","DOKUMA AKSESUAR","STANDART DIŞI","TRİKO ÖRME AKSESUAR"],kl:{"DERİ AKSESUAR":["KEY AKSESUAR CANTA BUYUK","KEY AKSESUAR CANTA KUCUK","KEY AKSESUAR CUZDAN","KEY AKSESUAR KEMER"],"DOKUMA AKSESUAR":["KEY AKSESUAR ATKI","KEY AKSESUAR DOKUMA ŞAPKA","KEY AKSESUAR ELDIVEN"],"STANDART DIŞI":["KEY AKSESUAR TAKI"],"TRİKO ÖRME AKSESUAR":["KEY AKSESUAR HAVLU","KEY ORME AKSESUAR BERE","KEY TRIKO AKSESUAR BERE","KEY TRIKO AKSESUAR ELDIVEN","KEY TRIKO AKSESUAR KAŞKOL"]}},
    "BUR":{bg:["ÇORAP"],kl:{"ÇORAP":["KEY AKSESUAR ÇORAP BABET","KEY AKSESUAR CORAP EV","KEY AKSESUAR CORAP PATIK","KEY AKSESUAR CORAP SNEAKER","KEY AKSESUAR CORAP SOKET"]}},
    "BUS":{bg:["BOXER","İÇ GİYİM"],kl:{"BOXER":["İÇGYM BASIC BOXER","İÇGYM KEY BOXER","İÇGYM SLİP"],"İÇ GİYİM":["İÇGYM KEY ÖRME FANİLA K.KOL","İÇGYM ORME ATLET","İÇGYM ORME FANILA U.KOL"]}},
    "BUSP":{bg:["PİJAMA"],kl:{"PİJAMA":["İÇGYM ÖRME PİJAMA TAKIM K.KOL-K.PAÇA","İÇGYM ÖRME PİJAMA TAKIM K.KOL-U.PAÇA","İÇGYM ÖRME PİJAMA TAKIM U.KOL-U.PAÇA","İÇGYM ÖRME PİJAMA TEK ALT KISA","İÇGYM ÖRME PİJAMA TEK ALT UZUN","İÇGYM ÖRME PİJAMA TEK ÜST","İÇGYM TERMAL ÜST","PİJAMA TERMAL ALT"]}}
  };

  const magData = erkekMAG[mag];
  if(!magData) return res.json({ok:false, error:'Geçersiz MAG'});

  const bgList = magData.bg.join(', ');
  let klSummary = '';
  Object.keys(magData.kl||{}).forEach(bg => {
    klSummary += bg + ': [' + magData.kl[bg].join(', ') + ']\n';
  });

  const feedbacksWithKW = feedbacks.map((f,i) => {
    const kw = kwResults[i]||{};
    return 'index='+i+': "'+f+'" → KW: BG='+(kw.bg||'?')+', KL='+(kw.kl||'?');
  }).join('\n');

  const prompt = `LC Waikiki mağaza ziyaret geri bildirim sınıflandırma sistemi.

MAG: ${mag}
Buyer Gruplar: ${bgList}
Klasmanlar:
${klSummary}

GÖREV: Her geri bildirimi ürün kategorisine göre sınıflandır.

TEMEL MANTIK — önce ürün tipini anla:
- "üst / tişört / gömlek / sweat / kazak / hirka / atlet / bluz" → üst giyim klasmanı
- "pantolon / chino / jean / şort / bermuda / alt" → alt giyim klasmanı  
- "mont / kaban / parka / yelek / ceket" → dış giyim klasmanı
- "v yaka / bisiklet yaka / polo yaka" → o yaka tipinin tişörtü — sadece bu kelimeler geçiyorsa o KL'yi seç
- "ince / kalın / orta" → ürün kalınlığı/ağırlığı — ürün tipini değiştirmez!
- ÖRME BG'de yaka KL'leri (BİSİKLET YAKA, V YAKA, POLO YAKA): metinde "bisiklet yaka", "v yaka", "polo yaka" geçmiyorsa KL null bırak. "tshirt/kısa kol/beyaz/renk" yaka tipini belirtmez!
- TRİKO BG: sadece "kazak", "hırka", "triko", "örgü" gibi net ifadeler varsa TRİKO seç. "çizgili", "desenli", "renkli" gibi özellikler tek başına TRİKO'yu belirtmez — bu durumda BG null veya GENEL bırak
- Genel kural: geri bildirimde ürün tipi NET belirtilmemişse (sadece renk/desen/kalite ifadesi varsa) BG null bırak
- Model adı (örn: Dubar, Scup, Zero, Ferjo) → o modelin ait olduğu kategori

KURALLAR:
1. Sadece yukarıdaki listede olan BG ve KL değerlerini kullan.
2. KW önerisi verilmiş ama sen BAĞIMSIZ düşün — geri bildirimin ürün tipine bak.
3. KW açıkça yanlışsa (üst ürün → pantolon klasmanı gibi) DÜZELt, high confidence ver.
4. KW mantıklıysa aynen kabul et.
5. Emin değilsen null bırak, uydurma.

Geri bildirimler (KW önerisiyle):
${feedbacksWithKW}

JSON döndür:
[{"index":0,"bg":"BG_ADI","kl":"KL_ADI_veya_null","confidence":"high/medium/low","reason":"1 satir aciklama"}]`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        messages: [{role:'user', content: prompt}]
      })
    });

    const data = await response.json();
    const text = data.content&&data.content[0] ? data.content[0].text : '';
    const clean = text.replace(/```json|```/g,'').trim();
    const results = JSON.parse(clean);
    res.json({ok:true, results});
  } catch(e) {
    res.json({ok:false, error: e.message});
  }
});




// Cleanup - duplicate ziyaretleri temizle
app.get('/admin/cleanup', (req, res) => {
  const key = req.query.key;
  const BACKUP_KEY = process.env.BACKUP_KEY || 'gemba2024';
  if(key !== BACKUP_KEY) return res.json({ok:false, error:'Unauthorized'});
  
  const data = loadData();
  let totalRemoved = 0;
  
  Object.keys(data.users||{}).forEach(function(uk){
    const visits = data.users[uk].visits||[];
    const seen = new Set();
    const unique = visits.filter(function(v){
      // Hash: mağaza + tüm notların metni
      const notesText = (v.notes||[]).map(function(n){return (n.tx||'').trim().toLowerCase();}).sort().join('|');
      const hash = (v.store||'').toLowerCase().trim() + '|' + notesText;
      if(seen.has(hash)){ totalRemoved++; return false; }
      seen.add(hash);
      return true;
    });
    data.users[uk].visits = unique;
  });
  
  saveData(data);
  res.json({ok:true, removed: totalRemoved});
});


// ── İstatistikler ────────────────────────────────────────────────────────────
app.get('/admin/stats', (req, res) => {
  const key = req.query.key;
  const BACKUP_KEY = process.env.BACKUP_KEY || 'gemba2024';
  if(key !== BACKUP_KEY) return res.json({ok:false, error:'Unauthorized'});

  const data = loadData();
  const users = data.users||{};
  const userKeys = Object.keys(users);

  let totalVisits = 0;
  let totalMail = 0;
  const userStats = [];

  userKeys.forEach(function(uk){
    const u = users[uk];
    const visits = u.visits||[];
    const mailCount = visits.filter(v => v.mailSent).length;
    totalVisits += visits.length;
    totalMail += mailCount;
    userStats.push({
      name: u.name,
      visits: visits.length,
      telegramVisits: visits.filter(v=>v.source==='telegram').length,
      manualVisits: visits.filter(v=>v.source!=='telegram').length,
      mailSent: mailCount,
      lastVisit: visits[0] ? visits[0].date : null
    });
  });

  res.json({
    ok: true,
    totalUsers: userKeys.length,
    totalVisits,
    totalMail,
    users: userStats.sort((a,b)=>b.visits-a.visits)
  });
});

// ── KW Rules ────────────────────────────────────────────────────────────────
const KW_FILE = path.join(path.dirname(process.env.DATA_PATH || '/app/data/data.json'), 'kw_rules.json');

function loadKWFile(){ try{ return JSON.parse(fs.readFileSync(KW_FILE,'utf8')); }catch(e){ return null; } }
function saveKWFile(data){ fs.writeFileSync(KW_FILE, JSON.stringify(data)); }

app.post('/kw/save', (req, res) => {
  const {rules} = req.body||{};
  if(!Array.isArray(rules)) return res.json({ok:false, error:'Gecersiz veri'});
  saveKWFile(rules);
  res.json({ok:true, count:rules.length});
});

app.get('/kw/load', (req, res) => {
  const rules = loadKWFile();
  res.json({ok:true, rules});
});


// Model auth endpoint
app.post('/models/auth', (req, res) => {
  const {pin} = req.body||{};
  const MODEL_PIN = process.env.MODEL_PIN || '1923';
  res.json({ok: pin === MODEL_PIN});
});


// ── Model adı çıkarma ────────────────────────────────────────────────────────
app.post('/ai/extract-models', async (req, res) => {
  const {feedbacks} = req.body||{};
  if(!feedbacks||!feedbacks.length) return res.json({ok:false,error:'Eksik'});

  const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;
  if(!ANTHROPIC_KEY) return res.json({ok:true, models: feedbacks.map(()=>null)});

  const prompt = `Aşağıdaki geri bildirimlerin her birinde geçen ÜRÜN MODEL ADINI bul.

Model adı: LC Waikiki ürünlerinin özel isimleri (örn: Scup, Zero, Ferjo, Jerno, Parma, Semper, Atina, Dubar, Neso, Iko vb.)
Bunlar genellikle büyük harfle başlar veya tamamen büyük harfle yazılır.

Eğer model adı yoksa null döndür.
Sadece JSON döndür:
[{"index":0,"model":"MODEL_ADI_veya_null"}]

Geri bildirimler:
${feedbacks.map((f,i)=>`${i}. "${f}"`).join('\n')}`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'x-api-key': ANTHROPIC_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 500,
        messages: [{role:'user', content: prompt}]
      })
    });
    const data = await response.json();
    const text = data.content&&data.content[0] ? data.content[0].text : '[]';
    const clean = text.replace(/```json|```/g,'').trim();
    const results = JSON.parse(clean);
    res.json({ok:true, models: results});
  } catch(e) {
    res.json({ok:true, models: feedbacks.map(()=>null)});
  }
});


// ── Telegram Bot Entegrasyonu ────────────────────────────────────────────────
const TG_USERS_FILE = path.join(path.dirname(DATA_FILE), 'tg_users.json');
const TG_TOKENS_FILE = path.join(path.dirname(DATA_FILE), 'tg_tokens.json');

// In-memory session storage
const tgSessions = {}; // {tgId: {store, mag, feedbacks, lastMsgAt, timeout}}

function getSession(tgId){ return tgSessions[tgId]||null; }
function setSession(tgId, data){ tgSessions[tgId] = {...data, lastMsgAt: Date.now()}; }
function clearSession(tgId){ delete tgSessions[tgId]; }

function loadTGUsers(){ try{ return JSON.parse(fs.readFileSync(TG_USERS_FILE,'utf8')); }catch(e){ return {}; } }
function saveTGUsers(d){ fs.writeFileSync(TG_USERS_FILE, JSON.stringify(d,null,2)); }
function loadTGTokens(){ try{ return JSON.parse(fs.readFileSync(TG_TOKENS_FILE,'utf8')); }catch(e){ return {}; } }
function saveTGTokens(d){ fs.writeFileSync(TG_TOKENS_FILE, JSON.stringify(d,null,2)); }

function sendTGMsg(chatId, text){
  if(!TG_TOKEN){ console.log('sendTGMsg: no token'); return; }
  if(!chatId){ console.log('sendTGMsg: no chatId'); return; }
  const body = JSON.stringify({chat_id:chatId, text, parse_mode:'HTML'});
  console.log('TG send to', chatId, ':', text.substring(0,60));
  const req = https.request({
    hostname:'api.telegram.org',
    path:`/bot${TG_TOKEN}/sendMessage`,
    method:'POST',
    headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}
  }, (res)=>{
    let d='';
    res.on('data',c=>d+=c);
    res.on('end',()=>{ try{ const r=JSON.parse(d); if(!r.ok) console.log('TG error:', r.description, 'chatId:', chatId); }catch(e){} });
  });
  req.on('error',(e)=>{ console.log('sendTGMsg req error:', e.message); });
  req.write(body); req.end();
}

// Token üret - ai-test'ten çağrılır
app.post('/telegram/create-token', (req, res) => {
  const {name, pin} = req.body||{};
  if(!name||!pin) return res.json({ok:false, error:'Ad ve PIN gerekli'});
  
  // Kullanıcıyı doğrula
  const data = loadData();
  const userKey = Object.keys(data.users||{}).find(k => {
    const u = data.users[k];
    return u.name === name && u.pin === pin;
  });
  if(!userKey) return res.json({ok:false, error:'Kullanıcı bulunamadı'});
  
  // Token üret
  const token = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
  const tokens = loadTGTokens();
  tokens[token] = {name, createdAt: Date.now(), expires: Date.now() + 10*60*1000}; // 10 dakika
  saveTGTokens(tokens);
  
  const botUsername = process.env.TELEGRAM_BOT_USERNAME || 'GembaGPTBot';
  res.json({ok:true, token, botUrl:`https://t.me/${botUsername}?start=${token}`});
});

// Token durumu kontrol
app.get('/telegram/check-token/:token', (req, res) => {
  const tokens = loadTGTokens();
  const t = tokens[req.params.token];
  if(!t) return res.json({ok:false, status:'invalid'});
  if(t.linkedTgId) return res.json({ok:true, status:'linked', name:t.name});
  if(Date.now() > t.expires) return res.json({ok:false, status:'expired'});
  res.json({ok:true, status:'pending'});
});

// Bağlı Telegram hesabını getir
app.post('/telegram/get-link', (req, res) => {
  const {name, pin} = req.body||{};
  if(!name||!pin) return res.json({ok:false});
  const data = loadData();
  const userKey = Object.keys(data.users||{}).find(k => {
    const u = data.users[k];
    return u.name === name && u.pin === pin;
  });
  if(!userKey) return res.json({ok:false});
  const tgUsers = loadTGUsers();
  const linked = Object.values(tgUsers).find(u => u.name === name);
  res.json({ok:true, linked: !!linked, tgName: linked ? linked.tgName : null});
});

// Telegram Webhook - bottan gelen mesajlar
// Deduplication - update_id dosyaya kayıt
const UPDATES_FILE = path.join(path.dirname(DATA_FILE), 'tg_updates.json');
function loadUpdates(){ try{ return JSON.parse(fs.readFileSync(UPDATES_FILE,'utf8')); }catch(e){ return []; } }
function saveUpdate(id){ const arr=loadUpdates(); if(!arr.includes(id)){ arr.push(id); if(arr.length>500) arr.splice(0, arr.length-500); fs.writeFileSync(UPDATES_FILE,JSON.stringify(arr)); } }
function isProcessed(id){ return loadUpdates().includes(id); }

app.post('/telegram/webhook', async (req, res) => {
  res.json({ok:true}); // Telegram'a hemen 200 ver
  const update = req.body;
  if(!update.message) return;
  
  // Duplicate check - update_id dosyada var mı?
  const updateId = update.update_id;
  if(updateId && isProcessed(updateId)){ console.log('Duplicate update ignored:', updateId); return; }
  if(updateId) saveUpdate(updateId);
  
  const msg = update.message;
  const chatId = msg.chat.id;
  const tgId = msg.from.id.toString();
  const text = (msg.text||'').trim();
  const tgName = [msg.from.first_name, msg.from.last_name].filter(Boolean).join(' ');

  // /start token ile gelen bağlantı
  if(text.startsWith('/start')){
    const token = text.split(' ')[1];
    if(!token){
      sendTGMsg(chatId, '👋 GembaGPT\'e hoş geldiniz!\n\nHesabınızı bağlamak için GembaGPT uygulamasını açın → Telegram sekmesi → QR kodu okutun.\n\n📋 Mesaj formatı:\n<code>MAĞAZA ADI\nReyon (Erkek/Kadın/Çocuk/Home/Bebek)\nMAG kodu (BUC, BUB, BUL...)\n- Geri bildirim 1\n- Geri bildirim 2</code>\n\nÖrnek:\n<code>T385-IST MALL OF ISTANBUL\nErkek\nBUC\n- Chino pantolon çeşidi az\n- Jerno modeli yok</code>');
      return;
    }
    const tokens = loadTGTokens();
    const t = tokens[token];
    if(!t){ sendTGMsg(chatId, '❌ Geçersiz veya süresi dolmuş bağlantı. Uygulamadan yeni QR kod alın.'); return; }
    if(Date.now() > t.expires){ sendTGMsg(chatId, '⏰ QR kodun süresi dolmuş. Uygulamadan yeni QR kod alın.'); return; }
    
    // Bağla
    const tgUsers = loadTGUsers();
    tgUsers[tgId] = {name: t.name, tgName, tgId, linkedAt: Date.now()};
    saveTGUsers(tgUsers);
    
    t.linkedTgId = tgId;
    tokens[token] = t;
    saveTGTokens(tokens);
    
    sendTGMsg(chatId, `✅ Merhaba <b>${t.name}</b>! Telegram hesabın GembaGPT'e bağlandı.\n\nArtık geri bildirim gönderebilirsin. Format:\n\n<b>MAĞAZA ADI</b>\n<b>MAG</b> (örn: BUC)\n- Geri bildirim 1\n- Geri bildirim 2`);
    return;
  }

  // Kullanıcı tanımlı mı?
  const tgUsers = loadTGUsers();
  const user = tgUsers[tgId];
  if(!user){
    sendTGMsg(chatId, '❌ Henüz bağlantı kurulmadı. GembaGPT uygulamasından QR kodu okutun.');
    return;
  }

  // Özel komutları kontrol et
  const lowerText = text.toLowerCase().trim();
  
  // İPTAL
  if(lowerText==='iptal' || lowerText==='cancel' || lowerText==='sil'){
    const sess = getSession(tgId);
    if(sess){
      clearSession(tgId);
      sendTGMsg(chatId, '🗑 Oturum iptal edildi. Yeni geri bildirim için mağaza adıyla başlayın.');
    } else {
      sendTGMsg(chatId, 'Aktif oturum yok.');
    }
    return;
  }

  // GÖNDER / TAMAM - mevcut oturumu analiz et
  if(lowerText==='gönder'||lowerText==='gonder'||lowerText==='tamam'||lowerText==='ok'||lowerText==='✓'){
    const sess = getSession(tgId);
    if(!sess||!sess.feedbacks||!sess.feedbacks.length){
      sendTGMsg(chatId, '❌ Gönderilecek geri bildirim yok. Önce mağaza ve geri bildirimleri yazın.');
      return;
    }
    clearSession(tgId);
    await processAnalysis(chatId, user, sess.store, sess.mag, sess.feedbacks, sess.reyon||'Erkek', sess.magBlocks||null);
    return;
  }

  // Mevcut oturum var mı?
  const existingSession = getSession(tgId);
  const lines = text.split('\n').map(l=>l.trim()).filter(Boolean);

  if(existingSession){
    // Oturuma ek geri bildirimler ekle
    const newFeedbacks = lines.map(l=>l.replace(/^[-•*\d.)]\s*/,'')).filter(function(l){return l.length>2;});
    if(newFeedbacks.length){
      existingSession.feedbacks.push(...newFeedbacks);
      setSession(tgId, existingSession);
      sendTGMsg(chatId, `➕ ${newFeedbacks.length} geri bildirim eklendi. Toplam: <b>${existingSession.feedbacks.length}</b>\n\nDevam etmek için daha fazla yazın veya <b>tamam</b> yazarak analiz edin.\n<b>iptal</b> yazarak oturumu silebilirsiniz.`);
    } else {
      sendTGMsg(chatId, '❓ Geri bildirim anlaşılamadı. Her satıra - ile başlayan geri bildirim yazın veya <b>tamam</b> yazın.');
    }
    return;
  }

  // Yeni oturum başlat
  // Format: MAĞAZA\nREYON\nMAG\n- fb1\n- fb2
  if(lines.length < 2){
    sendTGMsg(chatId, '👋 Merhaba <b>'+user.name+'</b>!\n\nFormat:\n<code>MAĞAZA ADI\nReyon (Erkek/Kadın vb)\nMAG (örn: BUC)\n- Geri bildirim 1\n- Geri bildirim 2</code>');
    return;
  }

  const store = lines[0];
  const REYONLAR = ['erkek','kadin','kadın','cocuk','çocuk','home','bebek'];
  const MAG_KODLARI = ['BUC','BUB','BUL','BUXL','BUMH','BUCF','BUGA','BUJD','BUJW','BUK','BUR','BUS','BUSP'];
  
  let reyon = 'Erkek', lineStart = 1;
  if(REYONLAR.includes(lines[1].toLowerCase().trim())){
    reyon = lines[1].trim();
    reyon = reyon.charAt(0).toUpperCase() + reyon.slice(1).toLowerCase();
    lineStart = 2;
  }

  // Çoklu MAG parse - MAG kodunu satır başında gördüğünde yeni blok başlat
  const magBlocks = []; // [{mag, feedbacks}]
  let currentMag = null;
  let currentFbs = [];

  for(let i = lineStart; i < lines.length; i++){
    const l = lines[i].trim();
    const lUp = l.toUpperCase();
    if(MAG_KODLARI.includes(lUp)){
      // Yeni MAG bloğu
      if(currentMag && currentFbs.length) magBlocks.push({mag:currentMag, feedbacks:currentFbs});
      else if(currentMag && !currentFbs.length){} // MAG var ama geri bildirim yok - atla
      currentMag = lUp;
      currentFbs = [];
    } else if(currentMag){
      const fb = l.replace(/^[-•*0-9.)]\s*/,'');
      if(fb.length > 2) currentFbs.push(fb);
    }
  }
  if(currentMag && currentFbs.length) magBlocks.push({mag:currentMag, feedbacks:currentFbs});

  // Geri bildirim yok ama MAG var - oturum aç
  if(magBlocks.length === 0 && currentMag){
    setSession(tgId, {store, reyon, mag:currentMag, feedbacks:[], magBlocks:[]});
    sendTGMsg(chatId, '📋 <b>'+store+'</b> / '+reyon+' / <b>'+currentMag+'</b> oturumu başlatıldı.\n\nGeri bildirimlerinizi yazın. Bitince <b>tamam</b> yazın.');
    return;
  }

  // Hiç MAG yok
  if(magBlocks.length === 0){
    sendTGMsg(chatId, '👋 Merhaba <b>'+user.name+'</b>!\n\nFormat:\n<code>MAĞAZA ADI\nReyon\nMAG (BUC, BUB...)\n- Geri bildirim 1</code>');
    return;
  }

  // Tek MAG ise eski yapıya uyumlu tut
  const mag = magBlocks[0].mag;
  const feedbacks = magBlocks.length === 1 ? magBlocks[0].feedbacks : magBlocks.map(b=>b.feedbacks).flat();

  // Özet göster ve onay bekle
  setSession(tgId, {store, reyon, mag, feedbacks, magBlocks});
  let preview = '📋 <b>'+store+'</b> — '+reyon+'\n\n';
  magBlocks.forEach(function(b){
    preview += '🏷 <b>'+b.mag+'</b>\n';
    b.feedbacks.forEach(function(f){ preview += '  • '+f+'\n'; });
    preview += '\n';
  });
  preview += '<b>tamam</b> → kaydet\n<b>iptal</b> → sil\nEklemek için devam yazın';
  sendTGMsg(chatId, preview);
  return;

  // Bu noktaya artık gelmiyor - processAnalysis fonksiyonu kullanılıyor
});


function getWeekNumber(d){
  const dd=new Date(Date.UTC(d.getFullYear(),d.getMonth(),d.getDate()));
  dd.setUTCDate(dd.getUTCDate()+4-(dd.getUTCDay()||7));
  return Math.ceil((((dd-new Date(Date.UTC(dd.getUTCFullYear(),0,1)))/86400000)+1)/7);
}

function kwMatchServer(text, mag){
  var n = text.toLowerCase()
    .replace(/ğ/g,'g').replace(/ü/g,'u').replace(/ş/g,'s')
    .replace(/ı/g,'i').replace(/ö/g,'o').replace(/ç/g,'c');

  var ERKEK_BG = {
    'BUC':['CHINO DUVARI','DIS GIYIM','DOKUMA UST','ORME','ORME BASIC','TRIKO','GENEL','LINE'],
    'BUB':['BLAZER CEKET','DENIM','DIS GIYIM','DOKUMA ALT','DOKUMA UST','ORME','TRIKO','GENEL','LINE'],
    'BUL':['BLAZER CEKET','DIS GIYIM','DOKUMA ALT','DOKUMA UST','ORME','TRIKO','GENEL','LINE'],
    'BUXL':['DENIM','DIS GIYIM','DOKUMA ALT','DOKUMA UST','ORME','TRIKO','GENEL','LINE'],
    'BUMH':['DOKUMA UST','ORME','YUZME GIYIM','GENEL','LINE'],
    'BUGA':['AKTIF SPOR','DIS GIYIM','DOKUMA ALT','GENEL','LINE'],
    'BUJD':['DENIM','GENEL','LINE'],
    'BUJW':['DENIM','DENIM DUVARI','GENEL','LINE'],
    'BUK':['DERI AKSESUAR','DOKUMA AKSESUAR','TRIKO ORME AKSESUAR','GENEL','LINE'],
    'BUR':['CORAP','GENEL','LINE'],
    'BUS':['BOXER','IC GIYIM','GENEL','LINE'],
    'BUSP':['PIJAMA','GENEL','LINE'],
    'BUCF':['BLAZER CEKET','DOKUMA ALT','DOKUMA UST','KRAVAT/PAPYON','GENEL','LINE']
  };

  var KW_MAP = [
    {kw:['chino','dar paca'],bg:'CHINO DUVARI'},
    {kw:['mont','kaban','parka','yelek','dis giyim'],bg:'DIS GIYIM'},
    {kw:['sweat','sweatshirt','kapuson','hoodie'],bg:'ORME BASIC'},
    {kw:['atlet','fanila'],bg:'ORME BASIC'},
    {kw:['sort','bermuda'],bg:'ORME BASIC'},
    {kw:['tisort','t-shirt','tshirt','polo','bisiklet yaka','v yaka'],bg:'ORME'},
    {kw:['hirka','kazak','triko'],bg:'TRIKO'},
    {kw:['gomlek','dokuma gomlek'],bg:'DOKUMA UST'},
    {kw:['jean','denim','kot'],bg:'DENIM'},
    {kw:['blazer','takim ceket'],bg:'BLAZER CEKET'},
    {kw:['pantolon','dokuma pantolon'],bg:'DOKUMA ALT'},
    {kw:['spor','aktif','kosu'],bg:'AKTIF SPOR'},
    {kw:['mayo','yuzme','deniz'],bg:'YUZME GIYIM'},
    {kw:['corap','soket'],bg:'CORAP'},
    {kw:['boxer','ic camasir'],bg:'BOXER'},
    {kw:['pijama'],bg:'PIJAMA'},
    {kw:['kemer','canta'],bg:'DERI AKSESUAR'},
  ];

  var bgList = (ERKEK_BG[mag]||['GENEL']);
  for(var i=0;i<KW_MAP.length;i++){
    var rule = KW_MAP[i];
    if(!bgList.includes(rule.bg)) continue;
    for(var j=0;j<rule.kw.length;j++){
      if(n.includes(rule.kw[j])) return rule.bg;
    }
  }
  return 'GENEL';
}


// ── Server-side KW puanlama (ai-test.html kwScore ile aynı mantık) ────────────
function nrServer(s){
  return (s||'').toLowerCase()
    .replace(/ğ/g,'g').replace(/ü/g,'u').replace(/ş/g,'s')
    .replace(/ı/g,'i').replace(/ö/g,'o').replace(/ç/g,'c')
    .replace(/i̇/g,'i').replace(/İ/g,'i');
}

function kwScoreServer(text, mag, reyon, modelHint, KW, MDB, ERKEK_DATA, RD_DATA){
  const n = nrServer(text);
  const md = reyon==='Erkek' ? (ERKEK_DATA[mag]||null) : (RD_DATA[reyon]||null);
  if(!md) return {bg:'GENEL', kl:null, src:'empty', score:0};

  const textWords = n.split(/[\s,.\/\-]+/).filter(p=>p.length>1);

  // 1. Model DB - hint ile exact search
  if(modelHint && MDB.length){
    const hn = nrServer(modelHint).replace(/[.,\-\/]/g,' ').trim();
    let found = null;
    // Exact match
    for(let i=0;i<MDB.length;i++){
      if(nrServer(MDB[i].model)===nrServer(modelHint) || MDB[i].normalized===hn){
        found=MDB[i]; break;
      }
    }
    // Partial match
    if(!found){
      for(let i=0;i<MDB.length;i++){
        const mn = MDB[i].normalized||'';
        if(mn.includes(hn)||hn.includes(mn)) { found=MDB[i]; break; }
      }
    }
    if(found && found.bg) return {bg:found.bg, kl:found.kl||null, src:'model', model:found.model, score:100};
  }

  const bgList = md.bg || [];

  // 2. BG ismi metinde var mı?
  for(let i=0;i<bgList.length;i++){
    const bgNorm = nrServer(bgList[i]);
    if(n.includes(bgNorm)){
      const klList = ((md.kl||{})[bgList[i]])||[];
      let bestKL=null, bestKLS=0;
      const STOP=['key','basic','cl','orme','dokuma','triko'];
      klList.forEach(kl=>{
        const klWords = nrServer(kl).replace(/[.\/\-]/g,' ').split(' ').filter(w=>w.length>3&&!STOP.includes(w));
        let s=0; klWords.forEach(w=>{if(n.includes(w))s+=w.length*2;});
        if(s>bestKLS){bestKLS=s;bestKL=kl;}
      });
      return {bg:bgList[i], kl:bestKL, src:'kw', score:80+bestKLS};
    }
  }

  // 3. KW kuralları - tam puanlama sistemi
  const scores = {};
  const STOP_WORDS=['key','basic','cl','orme','dokuma','triko','icgym','aksesuar','classic','sort','takim','gomlek','ince','kalin','orta','uzun','kisa','alt','ust','pant'];

  (KW||[]).forEach(rule=>{
    if(rule.mag && rule.mag!==mag) return;
    if(bgList.length && !bgList.includes(rule.bg)) return;
    let ruleScore=0;
    (rule.kw||[]).forEach(kw=>{
      const isPriority = typeof kw==='object' ? kw.p : (typeof kw==='string' && kw.charAt(0)==='!');
      const kwStr = typeof kw==='object' ? kw.w : (isPriority ? kw.slice(1) : kw);
      const kwn = nrServer(kwStr);
      let matchScore=0;
      if(n===kwn) matchScore=10;
      else if(n.includes(kwn)) matchScore=5;
      else if(kwn.includes(n)) matchScore=2;
      if(matchScore>0){
        ruleScore += isPriority && matchScore>=5 ? matchScore+100 : matchScore;
      }
    });
    if(ruleScore>0){
      const key = rule.bg+'|||'+(rule.kl||'');
      scores[key] = (scores[key]||0)+ruleScore;
    }
  });

  let bestKey=null, bestScore=0;
  Object.keys(scores).forEach(k=>{ if(scores[k]>bestScore){bestScore=scores[k];bestKey=k;} });
  if(bestKey && bestScore>0){
    const parts = bestKey.split('|||');
    let selectedBG = parts[0];
    let selectedKL = parts[1]||null;
    // ÖRME yaka KL - net yaka tipi yoksa null
    if(selectedKL){
      const klU = selectedKL.toUpperCase();
      const hasYakaKL = ['BİSİKLET YAKA','BISIKLET YAKA','V YAKA','POLO YAKA'].some(y=>klU.includes(y));
      if(hasYakaKL){
        const nLow = nrServer(text);
        // "polo yaka" veya "bisiklet yaka" açıkça yazılmışsa koru, sadece "polo" yetmez
        const hasExplicitYaka = nLow.includes('polo yaka')||nLow.includes('bisiklet yaka')||nLow.includes('v yaka')||nLow.includes('v-yaka');
        if(!hasExplicitYaka) selectedKL = null;
      }
    }
    return {bg:selectedBG, kl:selectedKL, src:'kw', score:bestScore};
  }

  // 4. KL isim tarama - puanlama
  const klData = md.kl||{};
  const klScores = [];
  Object.keys(klData).forEach(bg=>{
    (klData[bg]||[]).forEach(kl=>{
      const klNorm = nrServer(kl).replace(/[.\/\-]/g,' ');
      const klWords = klNorm.split(' ').filter(w=>w.length>2&&!STOP_WORDS.includes(w));
      let score=0;
      klWords.forEach(w=>{ if(n===w) score+=w.length*3; else if(n.includes(w)) score+=w.length*2; else if(w.includes(n)&&n.length>2) score+=n.length; });
      textWords.forEach(tw=>{ if(tw.length>2&&klNorm.includes(tw)) score+=tw.length; });
      if(score>0) klScores.push({bg,kl,score});
    });
  });
  if(klScores.length){
    klScores.sort((a,b)=>b.score-a.score);
    if(klScores[0].score>=4) return {bg:klScores[0].bg, kl:klScores[0].kl, src:'kw', score:klScores[0].score};
  }

  return {bg:'GENEL', kl:null, src:'empty', score:0};
}

async function processAnalysis(chatId, user, store, mag, feedbacks, reyon, magBlocks){
  try{
    const wn = getWeekNumber(new Date());
    // Çoklu MAG desteği
    let visitNotes = [];
    if(magBlocks && magBlocks.length > 0){
      magBlocks.forEach(function(block, bi){
        block.feedbacks.forEach(function(f, fi){
          visitNotes.push({id:Date.now()+(bi*100+fi), reyon:reyon||'Erkek', mag:block.mag, bg:null, kl:null, tx:f, photos:[], analyzed:false});
        });
      });
    } else {
      visitNotes = feedbacks.map(function(f, i){
        return {id:Date.now()+i, reyon:reyon||'Erkek', mag:mag, bg:null, kl:null, tx:f, photos:[], analyzed:false};
      });
    }
    const visit = {
      id:Date.now(), store, reyon:reyon||'Erkek', week:wn,
      date:new Date().toLocaleString('tr-TR',{timeZone:'Europe/Istanbul',hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit',year:'numeric'}), user:user.name,
      notes:visitNotes, source:'telegram', analyzed:false
    };
    const dbData = loadData();
    const userKey = Object.keys(dbData.users||{}).find(k=>{ const u=dbData.users[k]; return u.name===user.name || (u.name||'').toLowerCase()===(user.name||'').toLowerCase() || k===(user.name||'').trim().toLowerCase().replace(/\s+/g,'_'); });
    if(!userKey){
      sendTGMsg(chatId, '❌ Kullanıcı bulunamadı. QR kod ile yeniden bağlanın.');
      return;
    }
    if(!dbData.users[userKey].visits) dbData.users[userKey].visits=[];
    // Duplicate check - sadece birebir aynı içerik
    const recent = dbData.users[userKey].visits.slice(0,3);
    const fbHash = feedbacks.join('|||');
    const isDup = recent.some(function(v){
      const vHash = (v.notes||[]).map(function(n){return n.tx;}).join('|||');
      return vHash===fbHash && (Date.now()-v.id)<60000; // Sadece 1 dakika içinde birebir aynı
    });
    if(isDup){
      console.log('Duplicate blocked:', store);
      sendTGMsg(chatId, '✅ Bu geri bildirimler zaten kaydedildi!\nhttps://gembaapt.up.railway.app/ai-test.html');
      return;
    }
    dbData.users[userKey].visits.unshift(visit);
    if(dbData.users[userKey].visits.length>100) dbData.users[userKey].visits.splice(100);
    saveData(dbData);
    console.log('Visit saved:', store, mag, feedbacks.length, 'for', user.name);
    sendTGMsg(chatId, '✅ '+feedbacks.length+' geri bildirim kaydedildi!\nAnaliz için uygulamayı açın:\nhttps://gembaapt.up.railway.app/ai-test.html');
  }catch(e){
    console.log('processAnalysis err:', e.message);
    sendTGMsg(chatId, '❌ Kayıt hatası: '+e.message);
  }
}

// Webhook ayarla
app.get('/telegram/set-webhook', (req, res) => {
  if(!TG_TOKEN) return res.json({ok:false, error:'Token yok'});
  const webhookUrl = `${process.env.RAILWAY_PUBLIC_DOMAIN ? 'https://'+process.env.RAILWAY_PUBLIC_DOMAIN : 'https://gembaapt.up.railway.app'}/telegram/webhook`;
  const body = JSON.stringify({url: webhookUrl});
  const apiReq = https.request({
    hostname:'api.telegram.org',
    path:`/bot${TG_TOKEN}/setWebhook`,
    method:'POST',
    headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}
  },(apiRes)=>{
    let data='';
    apiRes.on('data',d=>data+=d);
    apiRes.on('end',()=>res.json(JSON.parse(data)));
  });
  apiReq.on('error',e=>res.json({ok:false,error:e.message}));
  apiReq.write(body); apiReq.end();
});

// ── Model DB ────────────────────────────────────────────────────────────────
const MODEL_FILE = process.env.DATA_PATH
  ? path.join(path.dirname(process.env.DATA_PATH || '/app/data/data.json'), 'models.json')
  : path.join('/app/data', 'models.json');

function loadModels(){
  try{ return JSON.parse(fs.readFileSync(MODEL_FILE,'utf8')); }
  catch(e){ return []; }
}
function saveModels(data){
  fs.writeFileSync(MODEL_FILE, JSON.stringify(data));
}

// Model listesini kaydet
app.post('/models/save', (req, res) => {
  const {models} = req.body||{};
  if(!Array.isArray(models)) return res.json({ok:false, error:'Geçersiz veri'});
  saveModels(models);
  res.json({ok:true, count:models.length});
});

// Model listesini yükle
app.get('/models/load', (req, res) => {
  const models = loadModels();
  res.json({ok:true, models});
});

// ── Backup / Restore ─────────────────────────────────────────────────────────
const BACKUP_KEY = process.env.BACKUP_KEY || 'gemba2024';

// Backup indir: /admin/backup?key=gemba2024
app.get('/admin/backup', (req, res) => {
  if(req.query.key !== BACKUP_KEY) return res.status(403).send('Yetkisiz');
  const data = loadData();
  const filename = 'gemba_backup_' + new Date().toISOString().slice(0,10) + '.json';
  res.setHeader('Content-Disposition', 'attachment; filename="' + filename + '"');
  res.setHeader('Content-Type', 'application/json');
  res.send(JSON.stringify(data, null, 2));
});

// Restore: POST /admin/restore?key=gemba2024
app.post('/admin/restore', (req, res) => {
  if(req.query.key !== BACKUP_KEY) return res.status(403).send('Yetkisiz');
  const data = req.body;
  if(!data||!data.users) return res.status(400).json({ok:false, error:'Gecersiz veri'});
  saveData(data);
  const count = Object.keys(data.users).length;
  res.json({ok:true, message: count + ' kullanici geri yuklendi'});
});

// ── Static ───────────────────────────────────────────────────────────────────
app.get('/gemba.png',(req,res)=>{
  const file=path.join(__dirname,'gemba.png');
  if(fs.existsSync(file)){res.setHeader('Content-Type','image/png');res.sendFile(file);}
  else res.status(404).send('Not found');
});
app.get('/manifest.json',(req,res)=>{
  res.setHeader('Content-Type','application/manifest+json');
  res.sendFile(path.join(__dirname,'manifest.json'));
});
app.use(express.static(path.join(__dirname)));
app.get('/ai-test.html',(req,res)=>res.sendFile(path.join(__dirname,'ai-test.html')));
app.get('*',(req,res)=>res.sendFile(path.join(__dirname,'index.html')));

app.listen(PORT,()=>{
  console.log(`Server running on port ${PORT}`);
  // Startup cleanup - duplicate ziyaretleri temizle
  try{
    const d = loadData();
    let removed = 0;
    Object.keys(d.users||{}).forEach(function(uk){
      const visits = d.users[uk].visits||[];
      const seen = new Set();
      const unique = visits.filter(function(v){
        const notesText = (v.notes||[]).map(function(n){return (n.tx||'').trim().toLowerCase();}).sort().join('|');
        if(!notesText) return true; // notesiz ziyaretleri koru
        const hash = (v.store||'').toLowerCase().trim()+'|'+notesText;
        if(seen.has(hash)){removed++;return false;}
        seen.add(hash);
        return true;
      });
      d.users[uk].visits = unique;
    });
    if(removed>0){ saveData(d); console.log('Startup cleanup: removed', removed, 'duplicate visits'); }
  }catch(e){ console.log('Cleanup err:', e.message); }
  console.log('Telegram:', TG_TOKEN?'configured':'not configured');
  console.log('Files:', fs.readdirSync(__dirname).filter(f=>!f.includes('node_modules')).join(', '));
  // Init data file
  // Klasoru olustur
  const dataDir=path.dirname(DATA_FILE);
  if(!fs.existsSync(dataDir)){
    fs.mkdirSync(dataDir,{recursive:true});
    console.log('Data dir created:', dataDir);
  }
  if(!fs.existsSync(DATA_FILE)) saveData({users:{}});
  console.log('Data file:', DATA_FILE);
});
