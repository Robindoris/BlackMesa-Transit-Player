"use strict";
const $ = s => document.querySelector(s);
const token = location.hash.slice(1) || sessionStorage.transit;
if (token) sessionStorage.transit = token;
history.replaceState(null, "", "/");
let state, tab = "library", filter = "", busy = false, onSubmit;
let directoryLayout = sessionStorage.directoryLayout === "list" ? "list" : "grid";
const art = new Set(["valve","cstrike","gearbox","redempt","svencoop","wantedsp","bshift_unlocked"]);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const button = (title, action, id="", cls="") => '<button class="'+cls+'" data-action="'+action+'" data-id="'+esc(id)+'">'+esc(title)+'</button>';
const msg = text => { $("#message").textContent = text; $("#message").hidden = !text; };
async function api(path, body) {
  const options = {headers:{"X-Session":token}};
  if (body !== undefined) {
    options.method = "POST";
    options.body = body instanceof File ? body : JSON.stringify(body);
  }
  const r = await fetch(path,options);
  const result = await r.json();
  if (!r.ok) throw Error(result.error || "Reopen the dashboard from its launcher.");
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

  const month = new Intl.DateTimeFormat(undefined, {month:"short"});
  const date = new Intl.DateTimeFormat(undefined, {dateStyle:"full"});
  const day = new Date(first);
  let weeks = "";
  while (day <= today) {
    const label = day.getDate() <= 7 ? month.format(day) : "";
    let cells = "";
    for (let row = 0; row < 7 && day <= today; row++, day.setDate(day.getDate() + 1)) {
      const seconds = daily.get(+day);
      const level = seconds == null ? 0 : seconds < 900 ? 1 : seconds < 3600 ? 2 : 3;
      const detail = date.format(day) + " · " + (seconds == null ? "No recorded play" : seconds ? duration(seconds) : "Game launched");
      cells += '<span class="play-day level-' + level + '" role="img" aria-label="' + esc(detail) + '" title="' + esc(detail) + '"></span>';
    }
    weeks += '<div class="play-week"><span class="play-month">' + esc(label) + '</span>' + cells + '</div>';
  }
  const count = daily.size + (daily.size === 1 ? " day played" : " days played");
  const scope = !history.activity && history.launches > sessions.length ? " · recent sessions only" : " · past year";
  return '<section class="card play-calendar"><div class="play-heading"><h3>Play calendar</h3><small>' +
    count + scope + '</small></div><div class="play-body"><div class="play-axis" aria-hidden="true"><span>Mon</span><span>Wed</span><span>Fri</span></div>' +
    '<div class="play-scroll"><div class="play-weeks">' + weeks + '</div></div></div>' +
    '<div class="play-key">Less playtime ' + [0,1,2,3].map(n => '<i class="play-day level-' + n + '"></i>').join("") + ' More</div></section>';
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
    ' · Personal peak: '+esc(m.peak)+'</small></div>').join("") :
    '<strong>No map score recorded yet</strong><small>Play on a monitored server with the launcher open to record your score and map together.</small>';
  let html = '<div class="section"><h2>All-time player performance</h2></div><div class="grid">'+
    '<article class="card info"><span>Top score</span><strong class="stat-value">'+esc(top ?? "—")+'</strong></article>'+
    '<article class="card info"><span>'+ (leaders.length > 1 ? "Best maps (tied)" : "Best map by peak score") +
    '</span>'+mapResult+'</article></div>';
  function table(title, headers, rows, empty, collapsible=false) {
    const body = rows.map(row => '<tr>'+row.map(value => '<td>'+esc(value ?? "—")+'</td>').join("")+'</tr>').join("");
    const content = body ? '<div class="card info"><table><thead><tr>'+
      headers.map(label => '<th>'+label+'</th>').join("")+'</tr></thead><tbody>'+body+'</tbody></table></div>' : '<div class="empty">'+empty+'</div>';
    if (collapsible) {
      const open = $("#map-history")?.open ? " open" : "";
      const count = rows.length + (rows.length === 1 ? " record" : " records");
      return '<details id="map-history" class="card map-history"'+open+'><summary><h2>'+title+
        ' <small>'+count+'</small></h2></summary>'+content+'</details>';
    }
    return '<div class="section"><h2>'+title+'</h2></div>'+content;
  }
  html += table("Personal server records", ["Server","Nickname","Peak score"],
    leaderboard.map(r => [r.server,r.nickname,r.peak]), "No leaderboard score recorded for your configured nicknames yet.");
  html += table("Most played maps", ["Map","Game mode","Recorded sessions","Your peak score"],
    maps.map(m => [m.map,modeName(m.mode),m.sessions,m.peak]), "No personal score with a known map has been recorded yet.");
  return html + table("Server map history", ["Map","Server","Peak players","Your observed peak"],
    serverMaps.map(m => [m.map,m.server,m.players,m.peak]), "No server maps recorded yet.", true);
}
function serverFacts(s, detailedOnly=false) {
  if(!s.status) return "";
  const values=detailedOnly?[]:[s.status==="Unavailable"?"Stats unavailable":s.status];
  if(s.map) values.push("Map · "+s.map);
  if(!detailedOnly && s.players!=null) values.push(s.players+" / "+s.capacity+" players");
  if(s.bots!=null) values.push(s.bots+" bots");
  if(s.ping!=null) values.push("Monitor ping · "+s.ping+" ms");
  if(s.timeLeft) values.push("Time left · "+s.timeLeft);
  if(s.nextMap && s.nextMap!=="[not yet voted on]") values.push("Next · "+s.nextMap);
  if(s.source) values.push(s.source);
  return '<div class="facts">'+values.map(value=>'<span>'+esc(value)+'</span>').join("")+'</div>';
}
function activityChart(buckets) {
  const peaks=buckets.map(b=>b.peak).filter(n=>n!=null);
  if(!peaks.length) return '<p class="empty">Hourly activity data is unavailable.</p>';
  const max=Math.max(1,...peaks);
  const hour=ts=>new Date(ts*1000).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
  const bars=buckets.map((b,i)=>{
    const height=b.peak==null?0:b.peak/max*78;
    const description=hour(b.start)+" · "+(b.peak==null?"No sample":b.peak+" players");
    return '<g><title>'+esc(description)+'</title><rect x="'+(i*20+2)+'" y="'+(82-Math.max(2,height))+'" width="16" height="'+Math.max(2,height)+'" fill="'+(b.peak==null?"#525458":"#f58b38")+'"/></g>';
  }).join("");
  return '<div class="card info"><strong>Peak occupancy · '+Math.max(...peaks)+' players</strong><svg class="activity-chart" viewBox="0 0 480 84" role="img" aria-label="Hourly peak occupied slots for the selected game modes">'+bars+'</svg><div class="axis"><span>'+esc(hour(buckets[0].start))+'</span><span>Local time · hourly peaks</span><span>'+esc(hour(buckets.at(-1).start))+'</span></div></div>';
}
function networkView() {
  const net=state.network;
  const servers=net.servers.filter(s=>!filter || s.mode===filter);
  const online=servers.filter(s=>s.status==="Online");
  const measured=servers.filter(s=>s.players!=null && s.capacity!=null && s.status!=="Offline");
  const players=measured.reduce((n,s)=>n+s.players,0), slots=measured.reduce((n,s)=>n+s.capacity,0);
  const tiles=[["Confirmed online",net.checked?online.length+" / "+servers.length:"—"],["Occupied slots",measured.length?players:"—"],["Reported capacity",measured.length?slots:"—"],["Fill rate",slots?Math.round(players/slots*100)+"%":"—"]];
  let html='<div class="section"><h2>Half-Life pack network</h2><div class="tools"><select id="filter" aria-label="Filter statistics by game mode"><option value="">All game modes</option>'+options(filter)+'</select>'+button("Refresh stats","liveServers")+'</div></div><div class="grid">'+tiles.map(([label,value])=>'<article class="card info"><span>'+label+'</span><strong class="stat-value">'+value+'</strong></article>').join("")+'</div><p class="meta">'+(net.checked?'Last checked '+esc(new Date(net.checked*1000).toLocaleTimeString()):'Fetching server statistics…')+'</p>';
  html+='<div class="section"><h2>Player activity · last 24 hours</h2></div>'+activityChart(net.peaks[filter || "all"] || []);
  html+='<div class="section"><h2>Live servers</h2></div><div class="grid">';
  if(!servers.length) html+='<div class="empty">BRUT.me lists no monitored server for this mode.</div>';
  const expanded=new Set(Array.from(document.querySelectorAll(".server-card[open]"),card=>card.dataset.server));
  for(const s of servers){
    const key=JSON.stringify([s.mode,s.address]);
    const status=s.status==="Unavailable"?"Stats unavailable":s.status || "Awaiting status";
    const occupancy=s.players==null?"":" · "+s.players+(s.capacity==null?"":" / "+s.capacity)+" players";
    html+='<article class="card live-server"><details class="server-card" data-server="'+esc(key)+'"'+(expanded.has(key)?" open":"")+'><summary><strong>'+esc(s.name)+'</strong><span class="meta">'+esc(status+occupancy)+'</span></summary>';
    html+='<div class="info"><span class="meta">'+esc(state.modes.find(m=>m.id===s.mode)?.name || s.mode)+' · '+esc(s.address)+'</span>'+serverFacts(s,true);
    if(s.capacity>0 && s.players!=null) html+='<progress aria-label="Occupied slots" value="'+Number(s.players)+'" max="'+Number(s.capacity)+'"></progress>';
    if(s.roster?.length) html+='<table><caption>Current players</caption><thead><tr><th>Player</th><th>Score</th><th>Session</th></tr></thead><tbody>'+s.roster.map(p=>'<tr><td>'+esc(p.name)+'</td><td>'+esc(p.score)+'</td><td>'+esc(p.time==null?"—":duration(p.time))+'</td></tr>').join("")+'</tbody></table>';
    else html+='<small class="meta">'+(s.players===0?"No players connected":"Roster unavailable")+'</small>';
    html+='</div></details>';
    const target=state.servers.find(v=>v.mode===s.mode && v.address===s.address);
    if(target && state.modes.find(m=>m.id===s.mode)?.installed && s.status!=="Offline")html+=button("Join server","join",target.id,"primary");
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
  $("#edition").textContent = "BRUT.me  /  HALF-LIFE PACK";
  $("#nav").innerHTML = button("Game library","library","",tab==="library"?"active":"") +
    button("Servers","servers","",tab==="servers"?"active":"") +
    button("Server stats","network","",tab==="network"?"active":"") +
    button("My stats","stats","",tab==="stats"?"active":"") +
    button("Catalog settings","settings","","right") + (state.url ? button("Refresh","refresh") : "") +
    button("Update dashboard","updateDashboard");
  const heroAction = button("▶  Launch default game","play","default","primary");
  let html = '<section class="hero"><span class="meta">'+"BRUT.me GAME PACK"+'</span><h1>'+
    (tab==="network"?"Server stats":tab==="stats"?"My stats":tab==="servers"?"Server directory":"Half-Life launcher")+'</h1>'+heroAction+'</section>';
  if (tab === "library") {
    html += '<div class="section"><h2>Game modes</h2><small>'+state.modes.length+' MODES</small></div><div class="grid">';
    for (const m of state.modes) {
      const release = state.mods[m.id];
      html += '<article class="card"><div class="art">'+(art.has(m.id)?'<img alt="" src="/art/'+m.id+'.jpg">':'λ')+'</div><div class="info"><span class="meta">'+
        (m.installed?"INSTALLED":release?"AVAILABLE TO DOWNLOAD":"MISSING FROM PACK")+'</span><h3>'+esc(m.name)+'</h3>'+
        (m.installed?button("▶  Play","play",m.id,"primary"):release?button("↓  Download","install",m.id):"")+'</div></article>';
    }
    html += '</div>';
  } else if (tab === "network") {
    html += networkView();
  } else if (tab === "stats") {
    const history=state.stats;
    html += '<div class="section"><h2>My Half-Life activity</h2></div><div class="grid">'+
      [["Recorded playtime",duration(history.seconds)],["Game launches",history.launches],["Server join requests",history.joins]]
      .map(([title,value])=>'<article class="card info"><span>'+esc(title)+'</span><strong class="stat-value">'+esc(value)+'</strong></article>').join("")+
      '</div><p class="meta">Recorded on this computer while the launcher is running.</p>'+playCalendar(history)+playerPerformance(history)+'<div class="section"><h2>Recent sessions</h2></div><div class="grid session-grid">';
    for (const session of history.recent) {
      html += '<article class="card session-card"><div><h3>'+esc(state.modes.find(m=>m.id===session.mode)?.name || session.mode)+(session.server?" · "+esc(session.server):"")+'</h3><small>'+
        esc(new Date(session.started*1000).toLocaleString())+'</small></div><div class="session-details"><span>Last score · '+esc(session.score ?? "Unrecorded")+'</span><span>'+esc(duration(session.seconds))+'</span></div></article>';
    }
    html += '</div>';
    if(!history.launches) html += '<div class="empty">Launch a pack mode or join a server to record your first session.</div>';
  } else {
    html += '<div class="section"><h2>Game servers</h2><div class="tools"><select id="filter" aria-label="Filter servers by game mode"><option value="">All game modes</option>'+options(filter)+'</select>'+
      '</div></div>';
    html += '<div class="feedbar"><span>BRUT.me · Half-Life'+(state.network.checked?' · Checked '+esc(new Date(state.network.checked*1000).toLocaleTimeString()):'')+'</span><div class="tools"><div class="layout-switch" role="group" aria-label="Server layout">'+
      ["grid","list"].map(layout=>'<button data-action="directoryLayout" data-id="'+layout+'" aria-pressed="'+(directoryLayout===layout)+'">'+(layout==="grid"?"Grid":"List")+'</button>').join("")+'</div>'+button("Refresh server stats","liveServers")+'</div></div>';
    const rows = state.servers.filter(s=>!filter || s.mode===filter);
    html += '<div class="'+(directoryLayout==="grid"?"grid directory-grid":"directory-list")+'">';
    for(const s of rows) {
      const m = state.modes.find(m=>m.id===s.mode);
      html += '<article class="row directory-row"><div class="server-description"><h3>'+esc(s.name)+'</h3><div class="server-meta"><small>'+esc(m.name)+' · '+esc(s.address)+'</small>'+serverFacts(s)+'</div></div>'+
        (m.installed?button("Join server","join",s.id,"primary"):state.mods[m.id]?button("Download mod","install",m.id):"Mod missing")+'</article>';
    }
    html += '</div>';
    if(!rows.length) html += '<div class="empty">'+(!state.url?"Set the catalog address to see published servers.":"No servers published for this selection.")+'</div>';
  }
  $("#view").innerHTML = html;
}
async function work(fn, pending, success) {
  if (busy) return;
  busy=true; msg(pending); $("#submit").disabled=true;
  try {state=await fn(); $("dialog").close(); render(); msg(success);}
  catch(e){msg(e.message);$("#error").textContent=e.message;try{state=await api("/api");render();}catch{}}
  finally{busy=false;$("#submit").disabled=false;}
}
const send = (action,data={})=>api("/action",{...data,action});
async function action(a,id) {
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
  if(a==="settings") return modal("Player catalog",input("url","Public catalog folder URL",state.url,"url","https://games.example.org/pack"),"Save and refresh",d=>send("configure",d));
  const s=state.servers.find(s=>s.id===id);
  if(a==="install") return modal("Install mod","<p>Download and install "+esc(state.mods[id].name)+" ("+(state.mods[id].bytes/1048576).toFixed(1)+" MiB) from your configured publisher?</p>","Install",()=>send(a,{mode:id}));
  if(a==="play"||a==="join") return work(()=>send("launch",{mode:s?.mode||id,server:s?.id}),"Launching…","Launch requested.");
  if(a==="refresh") work(()=>send(a),"Refreshing catalog…","Catalog refreshed.");
}
document.addEventListener("click",e=>{const b=e.target.closest("[data-action]");if(b)action(b.dataset.action,b.dataset.id);});
document.addEventListener("change",e=>{if(e.target.id==="filter"){filter=e.target.value;render();}});
$("#close").onclick=()=>{if(!busy)$("dialog").close();};
$("dialog").addEventListener("cancel",e=>{if(busy)e.preventDefault();});
$("#form").onsubmit=e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));work(()=>onSubmit(d),"Working…","Changes applied.");};
(async()=>{try{state=await api("/api");render();if(state.url)await work(()=>send("refresh"),"Refreshing catalog…","");}catch(e){msg(e.message);}})();

setInterval(()=>{if(!document.hidden)updateStatsView();},15000);
