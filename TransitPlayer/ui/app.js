"use strict";
const $ = s => document.querySelector(s);
const launchToken = location.hash.slice(1);
let token;
history.replaceState(null, "", "/");
let state, tab = "library", filter = "", busy = false, onSubmit;
let directoryLayout = sessionStorage.directoryLayout === "list" ? "list" : "grid";
const art = new Set(["valve","cstrike","gearbox","redempt","svencoop","wantedsp","bshift_unlocked"]);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const button = (title, action, id="", cls="") => '<button class="'+cls+'" data-action="'+action+'" data-id="'+esc(id)+'">'+esc(title)+'</button>';
let message = "";
const msg = text => { message = text; $("#message").textContent = t(text); $("#message").hidden = !text; };
function applyLanguage() {
  document.documentElement.lang = language;
  $(".brand small").textContent = t("TRANSIT SYSTEM");
  $("#nav").setAttribute("aria-label",t("Dashboard"));
  $("#languages").setAttribute("aria-label",t("Language"));
  $("#close").setAttribute("aria-label",t("Close"));
  for (const choice of document.querySelectorAll("#languages button")) {
    choice.setAttribute("aria-pressed",String(choice.dataset.id === language));
  }
  msg(message);
  if (state) render();
}
applyLanguage();
async function connect(credential) {
  const response = await fetch("/session", {headers: {"X-Session": credential || ""}});
  if (!response.ok) throw Error(t("Reopen the dashboard from its launcher."));
  const session = await response.json();
  token = session.session;
  if (session.pairing) localStorage.transitPairing = session.pairing;
}

async function api(path, body) {
  const options = {headers:{"X-Session":token}};
  if (body !== undefined) {
    options.method = "POST";
    options.body = body instanceof File ? body : JSON.stringify(body);
  }
  let r = await fetch(path,options);
  if (r.status === 403 && localStorage.transitPairing) {
    await connect(localStorage.transitPairing);
    options.headers["X-Session"] = token;
    r = await fetch(path,options);
  }
  const result = await r.json();
  if (!r.ok) throw Error(result.error || t("Reopen the dashboard from its launcher."));
  return result;
}
const options = selected => state.modes.map(m => '<option value="'+esc(m.id)+'" '+(selected===m.id?"selected":"")+'>'+esc(m.name)+'</option>').join("");
const input = (name,title,value="",type="text",hint="") => '<label>'+title+'<input required name="'+name+'" type="'+type+'" value="'+esc(value)+'" placeholder="'+esc(hint)+'"></label>';
function modal(title, fields, submit, callback) {
  $("#form h2").textContent = title; $("#fields").innerHTML = fields;
  $("#submit").textContent = submit; $("#error").textContent = ""; onSubmit = callback;
  $("dialog").showModal();
}
function duration(seconds) {
  if(seconds<60) return seconds+"s";
  const minutes=Math.floor(seconds/60);
  return minutes>=60 ? Math.floor(minutes/60)+"h "+minutes%60+"m" : minutes+"m";
}
function playCalendar(history) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const first = new Date(today);
  first.setDate(first.getDate() - (first.getDay() + 6) % 7 - 52 * 7);
  const daily = new Map();
  const sessions = history.activity ?? history.recent.map(s => [s.started, s.seconds]);
  for (const [started, seconds] of sessions) {
    const end = (started + Math.max(seconds, 1)) * 1000;
    let cursor = Math.max(first.getTime(), started * 1000);
    while (cursor < end) {
      const day = new Date(cursor);
      day.setHours(0, 0, 0, 0);
      if (day > today) break;
      const next = new Date(day);
      next.setDate(next.getDate() + 1);
      const stop = Math.min(end, next.getTime());
      daily.set(+day, (daily.get(+day) || 0) + (seconds ? (stop - cursor) / 1000 : 0));
      cursor = stop;
    }
  }

  const month = new Intl.DateTimeFormat(language, {month:"short"});
  const date = new Intl.DateTimeFormat(language, {dateStyle:"full"});
  const day = new Date(first);
  let weeks = "";
  while (day <= today) {
    const label = day.getDate() <= 7 ? month.format(day) : "";
    let cells = "";
    for (let row = 0; row < 7 && day <= today; row++, day.setDate(day.getDate() + 1)) {
      const seconds = daily.get(+day);
      const level = seconds == null ? 0 : seconds < 900 ? 1 : seconds < 3600 ? 2 : 3;
      const detail = date.format(day) + " · " + (seconds == null ? t("No recorded play") : seconds ? duration(seconds) : t("Game launched"));
      cells += '<span class="play-day level-' + level + '" role="img" aria-label="' + esc(detail) + '" title="' + esc(detail) + '"></span>';
    }
    weeks += '<div class="play-week"><span class="play-month">' + esc(label) + '</span>' + cells + '</div>';
  }
  const count = counted(daily.size,"day played","days played",["deň hrania","dni hrania","dní hrania"]);
  const scope = !history.activity && history.launches > sessions.length ? " · "+t("recent sessions only") : " · "+t("past year");
  return '<section class="card play-calendar"><div class="play-heading"><h3>'+t("Play calendar")+'</h3><small>' +
    count + scope + '</small></div><div class="play-body"><div class="play-axis" aria-hidden="true"><span>'+t("Mon")+'</span><span>'+t("Wed")+'</span><span>'+t("Fri")+'</span></div>' +
    '<div class="play-scroll"><div class="play-weeks">' + weeks + '</div></div></div>' +
    '<div class="play-key">'+t("Less playtime")+' ' + [0,1,2,3].map(n => '<i class="play-day level-' + n + '"></i>').join("") + ' '+t("More")+'</div></section>';
}
function playerPerformance(history) {
  const maps = history.maps || [];
  const leaderboard = history.leaderboard || [];
  const serverMaps = history.serverMaps || [];
  const scoredMaps = maps.filter(m => Number.isFinite(m.peak));
  const mapPeak = scoredMaps.reduce((peak, m) => peak == null || m.peak > peak ? m.peak : peak, null);
  const leaders = scoredMaps.filter(m => m.peak === mapPeak);
  const top = leaderboard.reduce((peak, row) => peak == null || row.peak > peak ? row.peak : peak, mapPeak);
  const modeName = id => state.modes.find(m => m.id === id)?.name || id;
  const mapResult = leaders.length ? leaders.map(m =>
    '<div><strong class="stat-value">'+esc(m.map)+'</strong><br><small>'+esc(modeName(m.mode))+
    ' · '+t("Personal peak")+': '+esc(m.peak)+'</small></div>').join("") :
    '<strong>'+t("No map score recorded yet")+'</strong><small>'+t("Play on a monitored server with the launcher open to record your score and map together.")+'</small>';
  let html = '<div class="section"><h2>'+t("All-time player performance")+'</h2></div><div class="grid">'+
    '<article class="card info"><span>'+t("Top score")+'</span><strong class="stat-value">'+esc(top ?? "—")+'</strong></article>'+
    '<article class="card info"><span>'+ (leaders.length > 1 ? t("Best maps (tied)") : t("Best map by peak score")) +
    '</span>'+mapResult+'</article></div>';
  function table(title, headers, rows, empty, collapsible=false) {
    const body = rows.map(row => '<tr>'+row.map(value => '<td>'+esc(value ?? "—")+'</td>').join("")+'</tr>').join("");
    const content = body ? '<div class="card info"><table><thead><tr>'+
      headers.map(label => '<th>'+label+'</th>').join("")+'</tr></thead><tbody>'+body+'</tbody></table></div>' : '<div class="empty">'+empty+'</div>';
    if (collapsible) {
      const open = $("#map-history")?.open ? " open" : "";
      const count = counted(rows.length,"record","records",["záznam","záznamy","záznamov"]);
      return '<details id="map-history" class="card map-history"'+open+'><summary><h2>'+title+
        ' <small>'+count+'</small></h2></summary>'+content+'</details>';
    }
    return '<div class="section"><h2>'+title+'</h2></div>'+content;
  }
  html += table(t("Personal server records"), [t("Server"),t("Nickname"),t("Peak score")],
    leaderboard.map(r => [r.server,r.nickname,r.peak]), t("No leaderboard score recorded for your configured nicknames yet."));
  html += table(t("Most played maps"), [t("Map"),t("Game mode"),t("Recorded sessions"),t("Your peak score")],
    maps.map(m => [m.map,modeName(m.mode),m.sessions,m.peak]), t("No personal score with a known map has been recorded yet."));
  return html + table(t("Server map history"), [t("Map"),t("Server"),t("Peak players"),t("Your observed peak")],
    serverMaps.map(m => [m.map,m.server,m.players,m.peak]), t("No server maps recorded yet."), true);
}
function serverFacts(s, detailedOnly=false) {
  if(!s.status) return "";
  const values=detailedOnly?[]:[s.status==="Unavailable"?t("Stats unavailable"):t(s.status)];
  if(s.map) values.push(t("Map")+" · "+s.map);
  if(!detailedOnly && s.players!=null) values.push(s.players+" / "+counted(s.capacity,"player","players",["hráč","hráči","hráčov"]));
  if(s.bots!=null) values.push(counted(s.bots,"bot","bots",["bot","boti","botov"]));
  if(s.ping!=null) values.push(t("Monitor ping")+" · "+s.ping+" ms");
  if(s.timeLeft) values.push(t("Time left")+" · "+s.timeLeft);
  if(s.nextMap && s.nextMap!=="[not yet voted on]") values.push(t("Next")+" · "+s.nextMap);
  if(s.source) values.push(t(s.source));
  return '<div class="facts">'+values.map(value=>'<span>'+esc(value)+'</span>').join("")+'</div>';
}
function activityChart(buckets) {
  const peaks=buckets.map(b=>b.peak).filter(n=>n!=null);
  if(!peaks.length) return '<p class="empty">'+t("Hourly activity data is unavailable.")+'</p>';
  const max=Math.max(1,...peaks);
  const hour=ts=>new Date(ts*1000).toLocaleTimeString(language, {hour:"2-digit",minute:"2-digit"});
  const bars=buckets.map((b,i)=>{
    const height=b.peak==null?0:b.peak/max*78;
    const description=hour(b.start)+" · "+(b.peak==null?t("No sample"):counted(b.peak,"player","players",["hráč","hráči","hráčov"]));
    return '<g><title>'+esc(description)+'</title><rect x="'+(i*20+2)+'" y="'+(82-Math.max(2,height))+'" width="16" height="'+Math.max(2,height)+'" fill="'+(b.peak==null?"#525458":"#f58b38")+'"/></g>';
  }).join("");
  return '<div class="card info"><strong>'+t("Peak occupancy")+' · '+counted(Math.max(...peaks),"player","players",["hráč","hráči","hráčov"])+'</strong><svg class="activity-chart" viewBox="0 0 480 84" role="img" aria-label="'+t("Hourly peak occupied slots for the selected game modes")+'">'+bars+'</svg><div class="axis"><span>'+esc(hour(buckets[0].start))+'</span><span>'+t("Local time · hourly peaks")+'</span><span>'+esc(hour(buckets.at(-1).start))+'</span></div></div>';
}
function networkView() {
  const net=state.network;
  const servers=net.servers.filter(s=>!filter || s.mode===filter);
  const online=servers.filter(s=>s.status==="Online");
  const measured=servers.filter(s=>s.players!=null && s.capacity!=null && s.status!=="Offline");
  const players=measured.reduce((n,s)=>n+s.players,0), slots=measured.reduce((n,s)=>n+s.capacity,0);
  const tiles=[[t("Confirmed online"),net.checked?online.length+" / "+servers.length:"—"],[t("Occupied slots"),measured.length?players:"—"],[t("Reported capacity"),measured.length?slots:"—"],[t("Fill rate"),slots?Math.round(players/slots*100)+"%":"—"]];
  let html='<div class="section"><h2>'+t("Half-Life pack network")+'</h2><div class="tools"><select id="filter" aria-label="'+t("Filter statistics by game mode")+'"><option value="">'+t("All game modes")+'</option>'+options(filter)+'</select>'+button(t("Refresh stats"),"liveServers")+'</div></div><div class="grid">'+tiles.map(([label,value])=>'<article class="card info"><span>'+label+'</span><strong class="stat-value">'+value+'</strong></article>').join("")+'</div><p class="meta">'+(net.checked?t("Last checked")+' '+esc(new Date(net.checked*1000).toLocaleTimeString(language)):t('Fetching server statistics…'))+'</p>';
  html+='<div class="section"><h2>'+t("Player activity · last 24 hours")+'</h2></div>'+activityChart(net.peaks[filter || "all"] || []);
  html+='<div class="section"><h2>'+t("Live servers")+'</h2></div><div class="grid">';
  if(!servers.length) html+='<div class="empty">'+t("BRUT.me lists no monitored server for this mode.")+'</div>';
  const expanded=new Set(Array.from(document.querySelectorAll(".server-card[open]"),card=>card.dataset.server));
  for(const s of servers){
    const key=JSON.stringify([s.mode,s.address]);
    const status=s.status==="Unavailable"?t("Stats unavailable"):t(s.status) || t("Awaiting status");
    const occupancy=s.players==null?"":" · "+(s.capacity==null?"":s.players+" / ")+counted(s.capacity ?? s.players,"player","players",["hráč","hráči","hráčov"]);
    html+='<article class="card live-server"><details class="server-card" data-server="'+esc(key)+'"'+(expanded.has(key)?" open":"")+'><summary><strong>'+esc(s.name)+'</strong><span class="meta">'+esc(status+occupancy)+'</span></summary>';
    html+='<div class="info"><span class="meta">'+esc(state.modes.find(m=>m.id===s.mode)?.name || s.mode)+' · '+esc(s.address)+'</span>'+serverFacts(s,true);
    if(s.capacity>0 && s.players!=null) html+='<progress aria-label="'+t("Occupied slots")+'" value="'+Number(s.players)+'" max="'+Number(s.capacity)+'"></progress>';
    if(s.roster?.length) html+='<table><caption>'+t("Current players")+'</caption><thead><tr><th>'+t("Player")+'</th><th>'+t("Score")+'</th><th>'+t("Session")+'</th></tr></thead><tbody>'+s.roster.map(p=>'<tr><td>'+esc(p.name)+'</td><td>'+esc(p.score)+'</td><td>'+esc(p.time==null?"—":duration(p.time))+'</td></tr>').join("")+'</tbody></table>';
    else html+='<small class="meta">'+(s.players===0?t("No players connected"):t("Roster unavailable"))+'</small>';
    html+='</div></details>';
    const target=state.servers.find(v=>v.mode===s.mode && v.address===s.address);
    if(target && state.modes.find(m=>m.id===s.mode)?.installed && s.status!=="Offline")html+=button(t("Join server"),"join",target.id,"primary");
    html+='</article>';
  }
  return html+'</div>';
}

let loadingView=false;
async function updateStatsView() {
  if(!state || $("dialog").open || busy || loadingView || !["stats","servers","network"].includes(tab)) return;
  const requested=tab;
  loadingView=true;
  try {
    const data=await send("liveServers",{history:requested==="network",personal:requested==="stats"});
    if(tab===requested && !busy){
      state.network=data.network; state.stats=data.stats; state.servers=data.servers; state.serverCheck=data.serverCheck; render();
    }
  } catch(e){msg(e.message);}
  finally{loadingView=false;}
}
function render() {
  $("#edition").textContent = t("BRUT.me  /  HALF-LIFE PACK");
  $("#nav").innerHTML = button(t("Game library"),"library","",tab==="library"?"active":"") +
    button(t("Servers"),"servers","",tab==="servers"?"active":"") +
    button(t("Server stats"),"network","",tab==="network"?"active":"") +
    button(t("My stats"),"stats","",tab==="stats"?"active":"") +
    button(t("Player name"),"playerName","","right") + button(t("Catalog settings"),"settings") + (state.url ? button(t("Refresh"),"refresh") : "") +
    button(t("Update dashboard"),"updateDashboard");
  const heroAction = button(t("▶  Launch default game"),"play","default","primary");
  let html = '<section class="hero"><span class="meta">'+t("BRUT.me GAME PACK")+'</span><h1>'+
    (tab==="network"?t("Server stats"):tab==="stats"?t("My stats"):tab==="servers"?t("Server directory"):t("Half-Life launcher"))+'</h1>'+heroAction+'</section>';
  if (tab === "library") {
    html += '<div class="section"><h2>'+t("Game modes")+'</h2><small>'+counted(state.modes.length,"MODE","MODES",["REŽIM","REŽIMY","REŽIMOV"])+'</small></div><div class="grid">';
    for (const m of state.modes) {
      const release = state.mods[m.id];
      html += '<article class="card"><div class="art">'+(art.has(m.id)?'<img alt="" src="/art/'+m.id+'.jpg">':'λ')+'</div><div class="info"><span class="meta">'+
        (m.installed?t("INSTALLED"):release?t("AVAILABLE TO DOWNLOAD"):t("MISSING FROM PACK"))+'</span><h3>'+esc(m.name)+'</h3>'+
        (m.installed?button(t("▶  Play"),"play",m.id,"primary"):release?button(t("↓  Download"),"install",m.id):"")+'</div></article>';
    }
    html += '</div>';
  } else if (tab === "network") {
    html += networkView();
  } else if (tab === "stats") {
    const history=state.stats;
    html += '<div class="section"><h2>'+t("My Half-Life activity")+'</h2></div><div class="grid">'+
      [[t("Recorded playtime"),duration(history.seconds)],[t("Game launches"),history.launches],[t("Server join requests"),history.joins]]
      .map(([title,value])=>'<article class="card info"><span>'+esc(title)+'</span><strong class="stat-value">'+esc(value)+'</strong></article>').join("")+
      '</div><p class="meta">'+t("Recorded on this computer while the launcher is running.")+'</p>'+playCalendar(history)+playerPerformance(history)+'<div class="section"><h2>'+t("Recent sessions")+'</h2></div><div class="grid session-grid">';
    for (const session of history.recent) {
      html += '<article class="card session-card"><div><h3>'+esc(state.modes.find(m=>m.id===session.mode)?.name || session.mode)+(session.server?" · "+esc(session.server):"")+'</h3><small>'+
        esc(new Date(session.started*1000).toLocaleString(language))+'</small></div><div class="session-details"><span>'+t("Last score")+' · '+esc(session.score ?? t("Unrecorded"))+'</span><span>'+esc(duration(session.seconds))+'</span></div></article>';
    }
    html += '</div>';
    if(!history.launches) html += '<div class="empty">'+t("Launch a pack mode or join a server to record your first session.")+'</div>';
  } else {
    html += '<div class="section"><h2>'+t("Game servers")+'</h2><div class="tools"><select id="filter" aria-label="'+t("Filter servers by game mode")+'"><option value="">'+t("All game modes")+'</option>'+options(filter)+'</select>'+
      '</div></div>';
    html += '<div class="feedbar"><span>BRUT.me · Half-Life'+(state.network.checked?' · '+t("Checked")+' '+esc(new Date(state.network.checked*1000).toLocaleTimeString(language)):'')+'</span><div class="tools"><div class="layout-switch" role="group" aria-label="'+t("Server layout")+'">'+
      ["grid","list"].map(layout=>'<button data-action="directoryLayout" data-id="'+layout+'" aria-pressed="'+(directoryLayout===layout)+'">'+(layout==="grid"?t("Grid"):t("List"))+'</button>').join("")+'</div>'+button(t("Refresh server stats"),"liveServers")+'</div></div>';
    const rows = state.servers.filter(s=>!filter || s.mode===filter);
    html += '<div class="'+(directoryLayout==="grid"?"grid directory-grid":"directory-list")+'">';
    for(const s of rows) {
      const m = state.modes.find(m=>m.id===s.mode);
      html += '<article class="row directory-row"><div class="server-description"><h3>'+esc(s.name)+'</h3><div class="server-meta"><small>'+esc(m.name)+' · '+esc(s.address)+'</small>'+serverFacts(s)+'</div></div>'+
        (m.installed?button(t("Join server"),"join",s.id,"primary"):state.mods[m.id]?button(t("Download mod"),"install",m.id):t("Mod missing"))+'</article>';
    }
    html += '</div>';
    if(!rows.length) html += '<div class="empty">'+(!state.url?t("Set the catalog address to see published servers."):t("No servers published for this selection."))+'</div>';
  }
  $("#view").innerHTML = html;
}
async function work(fn, pending, success) {
  if (busy) return;
  busy=true; msg(pending); $("#submit").disabled=true;
  try {state=await fn(); $("dialog").close(); render(); msg(success);}
  catch(e){msg(e.message);$("#error").textContent=t(e.message);try{state=await api("/api");render();}catch{}}
  finally{busy=false;$("#submit").disabled=false;}
}
const send = (action,data={})=>api("/action",{...data,action});
async function action(a,id) {
  if (a === "language" && ["en","sk"].includes(id)) {
    language = id;
    document.cookie = "bmt_player_language="+id+"; Path=/; Max-Age=31536000; SameSite=Strict";
    applyLanguage();
    return;
  }
  if (busy) return;
  if (["library","servers","modeServers","stats","network"].includes(a)) {
    tab=a==="modeServers"?"servers":a; filter=a==="modeServers"?id:""; render();updateStatsView();return;
  }
  if(a==="directoryLayout"){
    directoryLayout=id;
    sessionStorage.directoryLayout=id;
    render();
    document.querySelector('.layout-switch [aria-pressed="true"]').focus();
    return;
  }
  if(a==="liveServers") {updateStatsView();return;}
  if(a==="updateDashboard"){
    busy=true;
    msg("Checking for a dashboard update…");
    try { msg((await api("/update",{})).message); }
    catch(e){msg(e.message);}
    finally{busy=false;}
    return;
  }
  if(a==="playerName") return modal(t("Player name"),
    '<label>'+t("In-game name")+'<input autofocus name="playerName" maxlength="31" value="'+esc(state.playerName)+'" aria-describedby="nameHint"></label>'+
    '<p id="nameHint">'+t("Used when you play or join a server. Leave blank to use the game’s configured name.")+'</p>',
    t("Save name"),d=>send("setPlayerName",d));
  if(a==="settings") return modal(t("Player catalog"),input("url",t("Public catalog folder URL"),state.url,"url","https://games.example.org/pack"),t("Save and refresh"),d=>send("configure",d));
  const s=state.servers.find(s=>s.id===id);
  if(a==="install") return modal(t("Install mod"),"<p>"+esc(t("Download and install {mod} ({size} MiB) from your configured publisher?").replace(/\{(mod|size)\}/g, (_, key) => key === "mod" ? state.mods[id].name : (state.mods[id].bytes/1048576).toLocaleString(language,{minimumFractionDigits:1,maximumFractionDigits:1})))+"</p>",t("Install"),()=>send(a,{mode:id}));
  if(a==="play"||a==="join") return work(()=>send("launch",{mode:s?.mode||id,server:s?.id}),"Launching…","Launch requested.");
  if(a==="refresh") work(()=>send(a),"Refreshing catalog…","Catalog refreshed.");
}
document.addEventListener("click",e=>{const b=e.target.closest("[data-action]");if(b)action(b.dataset.action,b.dataset.id);});
document.addEventListener("change",e=>{if(e.target.id==="filter"){filter=e.target.value;render();}});
$("#close").onclick=()=>{if(!busy)$("dialog").close();};
$("dialog").addEventListener("cancel",e=>{if(busy)e.preventDefault();});
$("#form").onsubmit=e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));work(()=>onSubmit(d),"Working…","Changes applied.");};
(async()=>{try{await connect(launchToken || localStorage.transitPairing);state=await api("/api");render();if(state.url)await work(()=>send("refresh"),"Refreshing catalog…","");}catch(e){msg(e.message);}})();

setInterval(()=>{if(!document.hidden)updateStatsView();},15000);
