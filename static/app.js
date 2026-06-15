
/* DPP_V0141_STATE_SANITIZER_START */
(function(){
  if(window.__DPP_V0141_STATE_SANITIZER__) return;
  window.__DPP_V0141_STATE_SANITIZER__ = true;

  function canonName(name){
    var n = String(name || '').trim();
    var low = n.toLowerCase();

    if(low.indexOf('alpro protein chocolate') === 0) return 'Alpro Protein cacao';
    if(low === 'alpro protein cacao') return 'Alpro Protein cacao';

    if(low === 'huevos') return 'Huevo entero';
    if(low === 'huevo entero') return 'Huevo entero';

    if(low === 'platano') return 'Plátano';
    if(low === 'plátano') return 'Plátano';

    if(low === 'chocolate' || low === 'cacao' || low === 'cacao onzas estimado' || low === 'chocolate onzas estimado'){
      return 'Chocolate onzas estimado';
    }

    if(low === 'cafe con edulcorante' || low === 'café con edulcorante'){
      return 'Café con edulcorante';
    }

    return n;
  }

  var FIX = {
    'Alpro Protein cacao': {
      name:'Alpro Protein cacao', brand:'Alpro',
      kcal:69, protein:5, carbs:5.3, fat:2.8, sugar:5, salt:0.16, typical_g:250, purchased:1,
      source_note:'Etiqueta/ficha: 69 kcal, 5 g proteína, 5.3 g hidratos y 2.8 g grasa por 100 ml.',
      notes:'Bebida proteica sabor cacao. Vaso 250 ml = aprox. 172 kcal y 12.5 g proteína.'
    },
    'Huevo entero': {
      name:'Huevo entero', brand:'Casa',
      kcal:143, protein:12.6, carbs:0.7, fat:9.5, sugar:0, salt:0.35, typical_g:60, purchased:1,
      source_note:'Valor medio por 100 g.',
      notes:'1 huevo mediano-grande aprox. 60 g. Para 2 huevos registrar 120 g.'
    },
    'Plátano': {
      name:'Plátano', brand:'Fruta',
      kcal:89, protein:1.1, carbs:23, fat:0.3, sugar:12, salt:0.01, typical_g:120, purchased:1,
      source_note:'Valor medio por 100 g.',
      notes:'Peso comestible aproximado. Útil para desayuno/pre-entreno.'
    },
    'Chocolate onzas estimado': {
      name:'Chocolate onzas estimado', brand:'Estimado',
      kcal:550, protein:6, carbs:55, fat:32, sugar:48, salt:0.05, typical_g:20, purchased:0,
      source_note:'4 onzas estimadas como 20 g.',
      notes:'Snack dulce estimado. Registrar solo si se consume.'
    },
    'Café con edulcorante': {
      name:'Café con edulcorante', brand:'Casa',
      kcal:0, protein:0, carbs:0, fat:0, sugar:0, salt:0, typical_g:200, purchased:0,
      source_note:'Café sin azúcar.',
      notes:'Casi no suma.'
    }
  };

  function fixFood(f){
    if(!f || typeof f !== 'object') return f;
    var name = canonName(f.name || f.food_name);
    if(FIX[name]){
      return Object.assign({}, f, FIX[name]);
    }
    if(f.name !== undefined) f.name = name;
    if(f.food_name !== undefined) f.food_name = name;
    return f;
  }

  function fixRecursive(x){
    if(!x) return x;
    if(Array.isArray(x)) return x.map(fixRecursive);
    if(typeof x === 'object'){
      if(x.name || x.food_name) x = fixFood(x);
      Object.keys(x).forEach(function(k){
        if(k === 'name' || k === 'food_name') return;
        x[k] = fixRecursive(x[k]);
      });
      return x;
    }
    if(typeof x === 'string'){
      return x
        .replaceAll('Alpro Protein Chocolate onzas estimado onzas estimado', 'Alpro Protein cacao')
        .replaceAll('Alpro Protein Chocolate onzas estimado', 'Alpro Protein cacao')
        .replaceAll('Alpro Protein Chocolate', 'Alpro Protein cacao');
    }
    return x;
  }

  function sanitizeState(data){
    data = fixRecursive(data);

    if(data && Array.isArray(data.foods)){
      var seen = {};
      var clean = [];

      data.foods.forEach(function(raw){
        var f = fixFood(raw);
        var name = String(f.name || '').trim();
        var low = name.toLowerCase();

        if(low === 'huevos') return;
        if(low === 'chocolate') return;
        if(low === 'cacao') return;
        if(low.indexOf('alpro protein chocolate') === 0) return;

        var key = low;
        if(!seen[key]){
          seen[key] = f;
          clean.push(f);
        } else {
          var prev = seen[key];
          if(!Number(prev.purchased || 0) && Number(f.purchased || 0)){
            var idx = clean.indexOf(prev);
            if(idx >= 0) clean[idx] = f;
            seen[key] = f;
          }
        }
      });

      data.foods = clean;
    }

    return data;
  }

  var originalFetch = window.fetch;
  if(typeof originalFetch === 'function'){
    window.fetch = async function(input, init){
      var res = await originalFetch.apply(this, arguments);
      try{
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        if(String(url).indexOf('/api/state') === -1) return res;

        var clone = res.clone();
        var data = await clone.json();
        data = sanitizeState(data);

        return new Response(JSON.stringify(data), {
          status: res.status,
          statusText: res.statusText,
          headers: {'Content-Type':'application/json; charset=utf-8'}
        });
      }catch(e){
        return res;
      }
    };
  }

  try{
    if(localStorage.getItem('__DPP_V0141_STATE_CACHE_CLEAR__') !== '1'){
      Object.keys(localStorage).forEach(function(k){
        if(/dpp|diet|dieta|food|foods|state/i.test(k)){
          localStorage.removeItem(k);
        }
      });
      localStorage.setItem('__DPP_V0141_STATE_CACHE_CLEAR__', '1');
    }
  }catch(e){}
})();
/* DPP_V0141_STATE_SANITIZER_END */


let state=null; let page='home'; let mealItems=[]; let selectedDate=localStorage.getItem('selectedDate')||''; let selectedFoodPhoto='';
const PAGES=[['home','🏠','Resumen'],['register','⚡','Registrar'],['sport','🏋️','Deporte'],['templates','🍽️','Plantillas'],['foods','🥫','Alimentos'],['plan','📅','Plan'],['weights','⚖️','Historial peso'],['integrations','🔗','Integraciones'],['history','📚','Historial']];
const $=s=>document.querySelector(s); const fmt=n=>Number(n||0).toLocaleString('es-ES',{maximumFractionDigits:1});
const today=()=>state?.today||new Date().toISOString().slice(0,10); const nowHM=()=>state?.now||new Date().toTimeString().slice(0,5); const day=()=>selectedDate||today();
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}
async function api(path,opts={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},...opts}); if(!r.ok){let e='Error';try{e=(await r.json()).error||e}catch{} throw new Error(e)} return r.json()}
async function apiForm(path,form){const r=await fetch(path,{method:'POST',body:form}); if(!r.ok){let e='Error';try{e=(await r.json()).error||e}catch{} throw new Error(e)} return r.json()}
async function load(){state=await api('/api/state'); if(!selectedDate){selectedDate=today(); localStorage.setItem('selectedDate',selectedDate)} renderNav(); render()}
function renderNav(){ $('#nav').innerHTML=PAGES.map(([id,ico,label])=>`<button class="${page===id?'active':''}" data-page="${id}">${ico}<span>${label}</span></button>`).join(''); document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{page=b.dataset.page; renderNav(); render()}) }
function setTitle(t){$('#pageTitle').textContent=t}
function go(p){page=p;renderNav();render()}
function byDate(arr,d=day()){return arr.filter(x=>x.date===d)}
function mealTotals(meals){return meals.reduce((a,m)=>{a.kcal+=(m.totals?.kcal||0);a.protein+=(m.totals?.protein||0);a.oil+=(m.items||[]).filter(i=>/aceite/i.test(i.food_name)).reduce((x,i)=>x+Number(i.grams||0),0);return a},{kcal:0,protein:0,oil:0})}
function workoutTotals(ws){return ws.reduce((a,w)=>a+Number(w.kcal||0),0)}
function latestWeight(){return [...state.weights].sort((a,b)=>(b.date+b.time).localeCompare(a.date+a.time))[0]}
function officialWeights(){return state.weights.filter(w=>w.official).sort((a,b)=>(a.date+a.time).localeCompare(b.date+b.time))}
function foodByName(n){return state.foods.find(f=>f.name===n)} function foodById(id){return state.foods.find(f=>Number(f.id)===Number(id))}
function calcFood(f,g){const factor=Number(g||0)/100; return {food_id:f.id,food_name:f.name,grams:Number(g||0),kcal:f.kcal*factor,protein:f.protein*factor,carbs:f.carbs*factor,fat:f.fat*factor,sugar:f.sugar*factor,salt:f.salt*factor}}
function calcList(items){return items.reduce((a,i)=>{a.kcal+=Number(i.kcal||0);a.protein+=Number(i.protein||0);a.fat+=Number(i.fat||0);a.carbs+=Number(i.carbs||0);a.oil+=/aceite/i.test(i.food_name)?Number(i.grams||0):0;return a},{kcal:0,protein:0,fat:0,carbs:0,oil:0})}
function mealAdvice(items){const t=calcList(items); let cls='good',label='BIEN',text='Buen plato para bajar peso y mantener fuerza.'; if(t.kcal<250){cls='warn';label='POCO';text='Puede quedarse corto: añade proteína o fruta si toca entrenar.'} if(t.protein<20){cls='warn';label='MÁS PROTEÍNA';text='Sube pollo, huevos, atún, yogur o queso fresco.'} if(t.kcal>850){cls='bad';label='ALTO';text='Ración alta: reduce carbohidrato, pan o cantidad total.'} if(t.oil>10){cls='bad';label='ACEITE ALTO';text='Aceite alto: 5 g normal, 10 g máximo.'} if(t.kcal>=350&&t.kcal<=750&&t.protein>=25&&t.oil<=10){cls='good';label='BIEN';text='Buen plato: saciante, proteína decente y aceite controlado.'} return {cls,label,text,t}}
function assistantFor(d=day()){
  const meals=byDate(state.meals,d);
  const workouts=byDate(state.workouts,d);
  const mt=mealTotals(meals);
  const sport=workoutTotals(workouts);
  const lw=latestWeight();
  const tips=[];
  const names=meals.flatMap(m=>[m.name,m.notes||'',...(m.items||[]).map(i=>i.food_name)]).join(' ').toLowerCase();
  const hasSweet=/chocolate|galleta|piruleta|dulce|tirma/.test(names);
  const hasCarb=/pasta|arroz|pan|plátano|platano|tortita/.test(names);
  const dinnerDone=meals.some(m=>/cena/i.test(m.name));

  if(!lw) tips.push('Registra un peso oficial por la mañana para empezar tendencia.');
  else if(!lw.official) tips.push('Último peso es referencia: el bueno es por la mañana, después baño y antes de desayunar.');

  if(mt.protein<90) tips.push('Proteína baja: prioriza pollo, huevos, atún, yogur proteico, jamón cocido extra o queso fresco batido.');
  else if(mt.protein<130) tips.push('Proteína bastante bien, pero intenta acercarte a 130 g si hoy entrenas o cenas tarde.');
  else tips.push('Proteína cubierta hoy.');

  if(mt.oil>15) tips.push('Aceite alto hoy: próxima comida con sartén antiadherente y 0–5 g.');
  else if(mt.oil>10) tips.push('Aceite algo alto: no pases de 5 g en la siguiente comida.');

  if(hasSweet && sport<500) tips.push('Ya hubo dulce: cena limpia, sin pan/arroz extra y con verdura + proteína.');
  if(hasSweet && sport>=500) tips.push('Hubo dulce, pero también deporte: no castigues; cena proteica y carbo controlado si hay hambre real.');

  if(sport>=900) tips.push('Día de mucho gasto: puedes meter carbo controlado, pero mantén proteína y no conviertas el deporte en barra libre.');
  else if(sport>=300) tips.push('Buen gasto de actividad: recupera con proteína, no con picoteo.');

  if(mt.kcal>2300) tips.push('Kcal altas: resto del día limpio, agua/infusión y sin más snacks.');
  else if(mt.kcal<900 && !dinnerDone) tips.push('Aún vas bajo de comida registrada: no llegues con hambre brutal a la noche.');
  else if(mt.kcal>=900 && mt.kcal<=2100) tips.push('Día razonable: controla aceite, raciones y cena según hambre real.');

  if(!hasCarb && sport>=700) tips.push('Con ese deporte y pocos hidratos, una ración pequeña de arroz/pasta puede tener sentido.');

  return [...new Set(tips)].slice(0,6)
}
function render(){const titles={home:'Resumen',register:'Registrar / comida',templates:'Plantillas rápidas',foods:'Alimentos comprados',sport:'Registrar deporte',plan:'Plan semanal',weights:'Historial de peso',integrations:'Integraciones',history:'Historial completo'}; setTitle(titles[page]); if(page==='home')renderHome(); if(page==='register')renderRegister(); if(page==='templates')renderTemplates(); if(page==='foods')renderFoods(); if(page==='sport')renderSport(); if(page==='plan')renderPlan(); if(page==='weights')renderWeights(); if(page==='integrations')renderIntegrations(); if(page==='history')renderHistory()}
function metric(icon,title,value,sub){return `<div class="card metric"><span class="icon">${icon}</span><div><small>${title}</small><br><b>${value}</b></div><small>${sub}</small></div>`}
function dateBar(){const label=day()===today()?'Día de hoy':'Día seleccionado';return `<div class="datebar"><div class="field"><label>${label}</label><input id="dashDate" type="date" value="${day()}" onchange="selectedDate=this.value;localStorage.setItem('selectedDate',selectedDate);render()"></div><button class="btn secondary" onclick="selectedDate=today();localStorage.setItem('selectedDate',selectedDate);render()">Ir a hoy real</button><span class="muted">Así no se mezclan actividades de ayer con hoy.</span></div>`}
function quickActions(){return `<div class="quick-actions"><button class="quick primary" onclick="go('register')"><span>🍽️</span><b>Registrar comida</b><small>alimentos + gramos</small></button><button class="quick sport" onclick="go('sport')"><span>🏋️</span><b>Registrar entreno</b><small>minutos, kcal o Strava</small></button><button class="quick weight" onclick="go('weights')"><span>⚖️</span><b>Registrar peso</b><small>oficial o referencia</small></button><button class="quick" onclick="go('templates')"><span>⚡</span><b>Usar plantilla</b><small>cambia gramos y guarda</small></button></div>`}
function renderHome(){const lw=latestWeight(); const meals=byDate(state.meals); const workouts=byDate(state.workouts); const mt=mealTotals(meals); const sport=workoutTotals(workouts); $('#view').innerHTML=`${dateBar()}<div class="grid cols-4 dashboard-metrics">${metric('⚖️','Último peso',lw?`${fmt(lw.kg)} kg`:'—',lw?`${lw.date} ${lw.time} · ${lw.official?'oficial':'referencia'}`:'sin datos')}${metric('🍽️','Comido',fmt(mt.kcal),'kcal estimadas')}${metric('💪','Proteína',`${fmt(mt.protein)} g`,'objetivo 130–150 g')}${metric('🔥','Actividad',fmt(sport),'kcal del día seleccionado')}</div><div class="grid cols-2 home-main" style="margin-top:14px"><div class="card assistant compact-assistant"><h3>🤖 Asistente</h3><ul>${assistantFor().map(x=>`<li>${x}</li>`).join('')}</ul></div><div class="card"><h3>📉 Peso oficial</h3>${weightChart()}<p class="muted">Solo pesos oficiales de mañana para tendencia.</p></div></div><div class="day-columns"><section class="card day-panel"><div class="section-title compact-title"><div><h3>🍽️ Comidas</h3><p>${fmt(mt.kcal)} kcal · ${fmt(mt.protein)} g prot.</p></div><button class="btn small" onclick="go('register')">+ Comida</button></div><div class="compact-list">${meals.length?meals.map(mealCardCompact).join(''):'<div class="empty">Sin comidas.</div>'}</div></section><section class="card day-panel"><div class="section-title compact-title"><div><h3>🏋️ Actividad</h3><p>${fmt(sport)} kcal</p></div><button class="btn small" onclick="go('sport')">+ Entreno</button></div><div class="compact-list">${workouts.length?workouts.map(workoutCardCompact).join(''):'<div class="empty">Sin entrenos para este día.</div>'}</div></section></div><div class="footer-space"></div>`}
function weightChart(){const ws=officialWeights().slice(-10); if(ws.length<2)return '<div class="empty">Cuando tengas 2+ pesos oficiales aparece la gráfica.</div>'; const vals=ws.map(w=>+w.kg),min=Math.min(...vals)-.2,max=Math.max(...vals)+.2; const pts=ws.map((w,i)=>{const x=20+i*(260/(ws.length-1)); const y=150-((w.kg-min)/(max-min))*120; return `${x},${y}`}).join(' '); return `<svg class="chart" viewBox="0 0 300 175"><polyline points="${pts}" fill="none" stroke="#0b6b55" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>${ws.map((w,i)=>{const x=20+i*(260/(ws.length-1)); const y=150-((w.kg-min)/(max-min))*120; return `<circle cx="${x}" cy="${y}" r="5" fill="#0f8a6a"><title>${w.date}: ${w.kg}</title></circle>`}).join('')}<text x="18" y="168" font-size="11" fill="#697670">${ws[0].date}</text><text x="205" y="168" font-size="11" fill="#697670">${ws.at(-1).date}</text></svg>`}
function mealCard(m){return `<article class="list-card"><header><div><h4>${m.date} · ${m.time} · ${m.name}</h4><p class="muted">${m.notes||''}</p></div><button class="btn small danger" onclick="deleteMeal(${m.id})">×</button></header><div class="chips">${m.items.map(i=>`<span class="chip">${i.food_name} ${fmt(i.grams)}g</span>`).join('')}</div><b>${fmt(m.totals.kcal)} kcal · ${fmt(m.totals.protein)} g prot.</b></article>`}
function workoutCard(w){return `<article class="list-card"><header><div><h4>${w.date} · ${w.time} · ${w.name}</h4><p class="muted">${fmt(w.minutes)} min ${w.distance_km?`· ${fmt(w.distance_km)} km`:''} · ${w.notes||''}</p></div><button class="btn small danger" onclick="deleteWorkout(${w.id})">×</button></header><b>${fmt(w.kcal)} kcal</b></article>`}
function itemSummary(items){const shown=(items||[]).slice(0,3).map(i=>`${i.food_name} ${fmt(i.grams)}g`); const extra=(items||[]).length>3?` +${items.length-3}`:''; return shown.join(' · ')+extra}
function mealCardCompact(m){
  return window.DPPDashboardMealCard.mealCardCompact(m);
}
function workoutCardCompact(w){
  return window.DPPDashboardWorkoutCard.workoutCardCompact(w);
}
async function deleteMeal(id){if(!confirm('¿Borrar comida?'))return; await api('/api/meals/'+id,{method:'DELETE'}); toast('Comida borrada'); await load()} async function deleteWorkout(id){if(!confirm('¿Borrar entreno?'))return; await api('/api/workouts/'+id,{method:'DELETE'}); toast('Entreno borrado'); await load()}
function templateOptions(){return state.templates.map(t=>`<option value="${t.id}">${t.name}</option>`).join('')}
function renderRegister(){
  mealItems=[];
  $('#view').innerHTML=`<div class="register-grid">
    <section class="card register-main">
      <div class="section-title compact-title"><div><h3>🍽️ Nueva comida</h3><p>1) carga plantilla o busca alimentos · 2) cambia gramos · 3) guarda</p></div></div>
      <div class="row">
        <div class="field span-3"><label>Fecha</label><input id="mDate" type="date" value="${day()}"></div>
        <div class="field span-2"><label>Hora</label><input id="mTime" type="time" value="${nowHM()}"></div>
        <div class="field span-3"><label>Tipo</label><select id="mName"><option>Desayuno</option><option>Pre-comida</option><option>Comida</option><option>Merienda</option><option>Cena</option><option>Post-entreno</option></select></div>
        <div class="field span-4"><label>Notas</label><input id="mNotes" placeholder="pasta seca, tupper, post-HIIT..."></div>
      </div>
      <div class="template-loader">
        <div><b>⚡ Cargar plantilla</b><small>Se añade a esta comida y puedes cambiar gramos antes de guardar.</small></div>
        <select id="tplSelect"><option value="">Elegir plantilla...</option>${templateOptions()}</select>
        <button class="btn secondary" onclick="loadTemplateToMeal($('#tplSelect').value)">Cargar</button>
      </div>
      <div id="mealBuilder" class="meal-items"></div>
      <div class="sticky-actions">
        <button class="btn" onclick="saveMeal()">Guardar comida</button>
        <button class="btn secondary" onclick="saveMealAsTemplate()">Guardar como plantilla</button>
        <button class="btn secondary" onclick="clearMeal()">Limpiar</button>
      </div>
    </section>
    <aside class="card add-food-panel">
      <h3>➕ Añadir producto</h3>
      <div class="field"><label>Buscar alimento guardado</label><input id="foodSearch" placeholder="pollo, pasta, yogur..." oninput="renderSuggestions()"></div>
      <div class="field" style="margin-top:10px"><label>Gramos</label><input id="foodGrams" type="number" value="200"></div>
      <div id="suggestions" class="suggestions"></div>
      <p class="muted">Tip: si es una plantilla, cárgala y cambia solo gramos.</p>
    </aside>
    <section class="card weight-mini">
      <h3>⚖️ Peso rápido</h3>
      <div class="row">
        <div class="field span-4"><label>Fecha</label><input id="wDate" type="date" value="${today()}"></div>
        <div class="field span-3"><label>Hora</label><input id="wTime" type="time" value="${nowHM()}"></div>
        <div class="field span-3"><label>Kg</label><input id="wKg" type="number" step="0.01" placeholder="kg de hoy"></div>
        <div class="field span-2"><label>Tipo</label><select id="wOfficial"><option value="1">Oficial</option><option value="0">Referencia</option></select></div>
        <div class="field span-12"><label>Contexto</label><input id="wCtx" placeholder="mañana, después baño"></div>
      </div>
      <button class="btn" onclick="saveWeight()">Guardar peso</button>
    </section>
  </div>`;
  renderMealBuilder(); renderSuggestions();
}
function loadTemplateToMeal(id){
  if(!id){toast('Elige una plantilla');return}
  const t=state.templates.find(x=>String(x.id)===String(id));
  if(!t){toast('Plantilla no encontrada');return}
  let p={items:[]};try{p=JSON.parse(t.payload)}catch{}
  mealItems=(p.items||[]).map(it=>{const f=foodByName(it.food);return f?calcFood(f,it.grams):null}).filter(Boolean);
  if($('#mNotes')&&!$('#mNotes').value) $('#mNotes').value=t.notes||'';
  renderMealBuilder(); toast('Plantilla cargada: cambia gramos y guarda');
}
function addFood(id){const f=foodById(id); const g=Number($('#foodGrams').value||f.typical_g||100); mealItems.push(calcFood(f,g)); $('#foodSearch').value=''; $('#foodGrams').value=f.typical_g||100; renderMealBuilder(); renderSuggestions()}
function renderMealBuilder(){const advice=mealAdvice(mealItems); $('#mealBuilder').innerHTML=`${mealItems.length?mealItems.map((it,idx)=>`<div class="item-row"><div><b>${it.food_name}</b><small>${fmt(it.kcal)} kcal · ${fmt(it.protein)} g prot.</small></div><input type="number" value="${fmt(it.grams)}" onchange="changeMealGram(${idx},this.value)"><button class="btn small danger" onclick="removeMealItem(${idx})">×</button></div>`).join(''):'<div class="empty">Busca un producto y añádelo. Después solo cambias gramos.</div>'}<div class="totals"><span class="pill ${advice.cls}">${advice.label}</span><b>${fmt(advice.t.kcal)} kcal</b><b>${fmt(advice.t.protein)} g proteína</b><span class="muted">${advice.text}</span></div>`}
function changeMealGram(idx,val){const f=foodById(mealItems[idx].food_id); mealItems[idx]=calcFood(f,Number(val||0)); renderMealBuilder()} function removeMealItem(idx){mealItems.splice(idx,1); renderMealBuilder()} function clearMeal(){mealItems=[];renderMealBuilder()}
async function saveMeal(){if(!mealItems.length){toast('Añade alimentos');return} await api('/api/meals',{method:'POST',body:JSON.stringify({date:$('#mDate').value,time:$('#mTime').value,name:$('#mName').value,notes:$('#mNotes').value,items:mealItems.map(i=>({food_id:i.food_id,grams:i.grams}))})}); toast('Comida guardada'); selectedDate=$('#mDate').value; localStorage.setItem('selectedDate',selectedDate); await load(); page='home'; renderNav(); render()}
async function saveWeight(){await api('/api/weights',{method:'POST',body:JSON.stringify({date:$('#wDate').value,time:$('#wTime').value,kg:$('#wKg').value,official:$('#wOfficial').value==='1',context:$('#wCtx').value})}); toast('Peso guardado'); await load(); page='weights'; renderNav(); render()}
async function saveMealAsTemplate(){const name=prompt('Nombre de plantilla'); if(!name||!mealItems.length)return; await api('/api/templates',{method:'POST',body:JSON.stringify({name,notes:$('#mNotes').value,kind:'meal',payload:{items:mealItems.map(i=>({food:i.food_name,grams:i.grams}))}})}); toast('Plantilla guardada'); await load()}
function renderTemplates(){ $('#view').innerHTML=`<div class="section-title"><div><h3>Plantillas rápidas</h3><p>Cambia gramos y guarda en 2 clics</p></div></div><div class="grid cols-2">${state.templates.map(templateCard).join('')}</div>`}
function templateCard(t){let p={items:[]};try{p=JSON.parse(t.payload)}catch{} const items=(p.items||[]).map(it=>{const f=foodByName(it.food);return f?calcFood(f,it.grams):null}).filter(Boolean); const total=calcList(items); return `<div class="card template-card" data-template="${t.id}"><h3>${t.name}</h3><p class="muted">${t.notes||''}</p><div class="template-items">${items.map((it,idx)=>`<div class="template-item"><div><b>${it.food_name}</b><br><small>${fmt(it.kcal)} kcal · ${fmt(it.protein)} g prot.</small></div><input type="number" value="${fmt(it.grams)}" data-tgram="${idx}"></div>`).join('')}</div><div class="totals"><b>${fmt(total.kcal)} kcal</b><b>${fmt(total.protein)} g prot.</b></div><button class="btn" onclick="saveTemplateMeal(${t.id})">Guardar ahora</button></div>`}
async function saveTemplateMeal(id){const t=state.templates.find(x=>x.id===id); const p=JSON.parse(t.payload); const card=document.querySelector(`[data-template="${id}"]`); const grams=[...card.querySelectorAll('[data-tgram]')].map(i=>Number(i.value)); const items=p.items.map((it,idx)=>({food_name:it.food,grams:grams[idx]})); await api('/api/meals',{method:'POST',body:JSON.stringify({date:today(),time:nowHM(),name:t.name,notes:t.notes,items})}); toast('Plantilla registrada'); selectedDate=today(); localStorage.setItem('selectedDate',selectedDate); await load(); page='home'; renderNav(); render()}
function renderFoods(){
  selectedFoodPhoto='';
  $('#view').innerHTML=`<div class="grid cols-2">
    <div class="card"><h3>🥫 Nuevo alimento</h3>
      <div class="photo-box"><div><b>📷 Foto etiqueta</b><small>OCR real local: sube foto, revisa las sugerencias y guarda.</small></div><input id="fPhoto" type="file" accept="image/*" onchange="uploadFoodPhoto()"><div id="photoPreview"></div></div>
      <div class="row">
        <div class="field span-6"><label>Nombre</label><input id="fName" placeholder="Ej. Yogur Eroski +Proteína 120 g"></div>
        <div class="field span-6"><label>Marca</label><input id="fBrand" placeholder="Eroski, ElPozo..."></div>
        <div class="field span-3"><label>kcal / 100 g</label><input id="fKcal" type="number"></div>
        <div class="field span-3"><label>proteína / 100 g</label><input id="fProt" type="number"></div>
        <div class="field span-3"><label>hidratos</label><input id="fCarbs" type="number"></div>
        <div class="field span-3"><label>grasa</label><input id="fFat" type="number"></div>
        <div class="field span-3"><label>azúcar</label><input id="fSugar" type="number"></div>
        <div class="field span-3"><label>sal</label><input id="fSalt" type="number"></div>
        <div class="field span-3"><label>ración g</label><input id="fTypical" type="number" value="100"></div>
        <div class="field span-3"><label>Comprado</label><select id="fPurchased"><option value="1">Sí</option><option value="0">No</option></select></div>
        <div class="field span-12"><label>Nota etiqueta</label><textarea id="fSource" placeholder="Ej. Por unidad 120 g: 68 kcal, 10 g proteína..."></textarea></div>
        <div class="field span-12"><label>Uso</label><input id="fNotes" placeholder="Desayuno, merienda, tupper..."></div>
      </div>
      <button class="btn" onclick="saveFood()">Guardar alimento</button>
    </div>
    <div class="card note-box"><h3>📌 OCR de etiqueta</h3><p>Sube la foto de la etiqueta, copia los valores por 100 g o por ración y guarda. La foto queda asociada al producto para revisarla después.</p><p class="muted">OCR local activo: rellena solo valores plausibles. Revisa siempre antes de guardar.</p></div>
  </div>
  <div class="section-title"><div><h3>Alimentos guardados</h3><p>Se usan en Registrar para cambiar solo gramos.</p></div><input id="foodFilter" placeholder="filtrar..." style="max-width:300px" oninput="renderFoodList()"></div>
  <div id="foodList" class="grid cols-3"></div>`;
  renderFoodList();
}
function renderFoodList(){const q=($('#foodFilter')?.value||'').toLowerCase(); const foods=state.foods.filter(f=>(f.name+' '+f.brand+' '+f.source_note).toLowerCase().includes(q)); $('#foodList').innerHTML=foods.map(f=>`<div class="card food-card">${f.photo_path?`<img class="food-photo" src="${f.photo_path}" alt="foto etiqueta">`:''}<h3>${f.purchased?'✅':'🥫'} ${f.name}</h3><p class="muted">${f.brand||''}</p><div class="chips"><span class="chip">${fmt(f.kcal)} kcal/100g</span><span class="chip">${fmt(f.protein)} g prot</span><span class="chip">típico ${fmt(f.typical_g)} g</span></div><p class="source">${f.source_note||''}</p><p>${f.notes||''}</p></div>`).join('')}
async function uploadFoodPhoto(){
  const file=$('#fPhoto')?.files?.[0];
  if(!file)return;
  const form=new FormData();
  form.append('photo',file);
  try{
    const r=await apiForm('/api/food-photo-ocr',form);
    selectedFoodPhoto=r.photo_path;
    const text=r.ocr_text||'';
    const n=r.nutrition||{};
    if($('#photoPreview')){
      $('#photoPreview').innerHTML=`<img class="food-photo preview" src="${selectedFoodPhoto}" alt="foto etiqueta"><span class="pill good">foto guardada</span>${text?'<span class="pill good">OCR leído</span>':`<span class="pill warn">OCR sin texto</span>`}`;
    }
    if($('#labelText') && text) $('#labelText').value=text;
    const fill=(id,val)=>{const el=$(id); if(el && val!==undefined && val!==null && val!=='') el.value=String(val).replace('.',',').replace(',','.');};
    fill('#fKcal', n.kcal);
    fill('#fProt', n.protein);
    fill('#fCarbs', n.carbs);
    fill('#fFat', n.fat);
    fill('#fSugar', n.sugar);
    fill('#fSalt', n.salt);
    fill('#fTypical', n.typical_g);
    if($('#fSource') && text) $('#fSource').value=(text.length>900?text.slice(0,900)+'…':text);
    toast(text?'Foto guardada y OCR interpretado':'Foto guardada; revisa OCR manual');
  }catch(e){
    toast(e.message);
  }
}
async function saveFood(){await api('/api/foods',{method:'POST',body:JSON.stringify({name:$('#fName').value,brand:$('#fBrand').value,kcal:$('#fKcal').value,protein:$('#fProt').value,carbs:$('#fCarbs').value,fat:$('#fFat').value,sugar:$('#fSugar').value,salt:$('#fSalt').value,typical_g:$('#fTypical').value,purchased:$('#fPurchased').value==='1',source_note:$('#fSource').value,notes:$('#fNotes').value,photo_path:selectedFoodPhoto})}); toast('Alimento guardado'); await load(); page='foods'; renderNav(); render()}
function renderSport(){ $('#view').innerHTML=`<div class="grid cols-2"><div class="card"><h3>🏋️ Nuevo entreno</h3><div class="row"><div class="field span-4"><label>Fecha</label><input id="sDate" type="date" value="${today()}"></div><div class="field span-3"><label>Hora</label><input id="sTime" type="time" value="${nowHM()}"></div><div class="field span-5"><label>Ejercicio</label><select id="sName">${state.exercises.map(e=>`<option>${e.name}</option>`).join('')}</select></div><div class="field span-3"><label>Minutos</label><input id="sMin" type="number"></div><div class="field span-3"><label>Distancia km</label><input id="sKm" type="number"></div><div class="field span-3"><label>Calorías reloj</label><input id="sKcal" type="number" placeholder="vacío = estima"></div><div class="field span-3"><label>&nbsp;</label><button class="btn" onclick="saveWorkout()">Guardar</button></div><div class="field span-12"><label>Notas</label><input id="sNotes"></div></div></div><div class="card"><h3>➕ Nuevo ejercicio</h3><div class="row"><div class="field span-6"><label>Nombre</label><input id="eName"></div><div class="field span-3"><label>MET</label><input id="eMet" type="number" value="5"></div><div class="field span-3"><label>&nbsp;</label><button class="btn" onclick="saveExercise()">Guardar</button></div><div class="field span-12"><label>Notas</label><input id="eNotes"></div></div></div></div><div class="section-title"><h3>Historial deporte</h3></div><div class="list">${state.workouts.map(workoutCard).join('')}</div>`}
async function saveWorkout(){await api('/api/workouts',{method:'POST',body:JSON.stringify({date:$('#sDate').value,time:$('#sTime').value,name:$('#sName').value,minutes:$('#sMin').value,distance_km:$('#sKm').value,kcal:$('#sKcal').value,notes:$('#sNotes').value})}); toast('Entreno guardado'); selectedDate=$('#sDate').value; localStorage.setItem('selectedDate',selectedDate); await load(); page='home'; renderNav(); render()}
async function saveExercise(){await api('/api/exercises',{method:'POST',body:JSON.stringify({name:$('#eName').value,met:$('#eMet').value,notes:$('#eNotes').value})}); toast('Ejercicio guardado'); await load(); page='sport'; renderNav(); render()}
function renderPlan(){const p=state.plans[0]?JSON.parse(state.plans[0].payload):null; $('#view').innerHTML=`<div class="grid cols-2"><div class="card"><h3>📥 Importar plan semanal</h3><p class="muted">Pega JSON que te pase ChatGPT.</p><textarea id="planRaw" style="min-height:220px" placeholder='{"name":"Semana...","days":[...]}'></textarea><button class="btn" onclick="savePlan()">Importar plan</button></div><div class="card"><h3>📅 Plan actual</h3>${p?renderPlanPayload(p):'<div class="empty">Sin plan.</div>'}</div></div>`}
function renderPlanPayload(p){return `<h3>${p.name}</h3><p class="muted">${p.notes||''}</p><div class="grid">${(p.days||[]).map(d=>`<div class="plan-day"><b>${d.day}</b><p><b>Desayuno:</b> ${d.breakfast||''}</p><p><b>Comida:</b> ${d.lunch||''}</p><p><b>Merienda:</b> ${d.snack||''}</p><p><b>Cena:</b> ${d.dinner||''}</p></div>`).join('')}</div>`}
async function savePlan(){await api('/api/plans',{method:'POST',body:JSON.stringify({raw:$('#planRaw').value})}); toast('Plan importado'); await load(); page='plan'; renderNav(); render()}
function renderWeights(){const all=[...state.weights].sort((a,b)=>(b.date+b.time).localeCompare(a.date+a.time)); $('#view').innerHTML=`<div class="grid cols-2"><div class="card"><h3>📉 Gráfica peso oficial</h3>${weightChart()}<p class="muted">La tendencia usa solo pesos oficiales. Las referencias ayudan a entender variaciones por comida/agua.</p></div><div class="card"><h3>⚖️ Registrar peso</h3><div class="row"><div class="field span-4"><label>Fecha</label><input id="wDate" type="date" value="${today()}"></div><div class="field span-3"><label>Hora</label><input id="wTime" type="time" value="${nowHM()}"></div><div class="field span-3"><label>Kg</label><input id="wKg" type="number" step="0.01"></div><div class="field span-2"><label>Tipo</label><select id="wOfficial"><option value="1">Oficial</option><option value="0">Referencia</option></select></div><div class="field span-12"><label>Contexto</label><input id="wCtx"></div></div><button class="btn" onclick="saveWeight()">Guardar peso</button></div></div><div class="section-title"><h3>Historial de peso</h3></div><div class="list">${all.map(w=>`<div class="list-card"><header><div><h4>${w.date} ${w.time} · ${fmt(w.kg)} kg</h4><p class="muted">${w.official?'Oficial':'Referencia'} · ${w.context||''}</p></div><button class="btn small danger" onclick="deleteWeight(${w.id})">×</button></header></div>`).join('')}</div>`}
async function deleteWeight(id){if(!confirm('¿Borrar peso?'))return; await api('/api/weights/'+id,{method:'DELETE'}); toast('Peso borrado'); await load(); render()}

function renderIntegrations(){
  $('#view').innerHTML=`<div class="grid cols-2"><div class="card integration-card"><h3>🔗 Strava</h3><p class="muted">Sincroniza actividades autorizadas de tu cuenta. Los tokens se guardan solo en la Raspberry, dentro de data/.</p><div id="stravaStatus" class="empty">Comprobando Strava...</div><div class="action-row"><button class="btn" onclick="connectStrava()">Conectar Strava</button><button class="btn secondary" onclick="syncStrava()">Sincronizar 14 días</button></div></div><div class="card note-box"><h3>Privacidad</h3><p>El repositorio no sube data/, dieta.db, tokens ni .env. Strava requiere configurar credenciales en la Raspberry.</p><p class="muted">Zepp/Amazfit directo no tiene una API pública sencilla para actividades. Ruta práctica: Zepp → Strava → Dieta Pro.</p></div></div>`;
  loadStravaStatus();
}
async function loadStravaStatus(){
  try{
    const s=await api('/api/strava/status');
    $('#stravaStatus').innerHTML=`<div class="status ${s.connected?'ok':s.configured?'warn':'bad'}"><b>${s.connected?'Conectado':s.configured?'Configurado, falta conectar':'No configurado'}</b><span>${s.message}</span></div>`;
    window.__stravaConnectUrl=s.connect_url;
  }catch(e){$('#stravaStatus').textContent='No se pudo comprobar Strava: '+e.message}
}
function connectStrava(){ if(window.__stravaConnectUrl) location.href=window.__stravaConnectUrl; else toast('Primero configura Strava en .env') }
async function syncStrava(){ try{const r=await api('/api/strava/sync',{method:'POST',body:JSON.stringify({days:14})}); toast(`Strava sincronizado: ${r.imported} nuevas actividades`); await load(); page='home'; renderNav(); render()}catch(e){toast('Strava: '+e.message)} }

function renderHistory(){ $('#view').innerHTML=`<div class="grid cols-2"><div><div class="section-title"><h3>Comidas</h3></div><div class="list">${state.meals.map(mealCard).join('')}</div></div><div><div class="section-title"><h3>Deporte</h3></div><div class="list">${state.workouts.map(workoutCard).join('')}</div></div></div>`}
$('#btnRefresh').onclick=load; load().catch(e=>{document.body.innerHTML='<pre style="padding:20px">Error cargando app: '+e.message+'</pre>'})


// V002_STRAVA_MANUAL_IMPORT_UI
let __stravaPreview = [];

function renderIntegrations(){
  const to = today();
  const from = new Date(Date.now() - 14 * 86400000).toISOString().slice(0,10);

  $('#view').innerHTML = `
    <div class="grid cols-2">
      <div class="card integration-card">
        <h3>🔗 Strava</h3>
        <p class="muted">Conecta Strava, elige fechas, revisa actividades e importa solo las que marques.</p>

        <div id="stravaStatus" class="empty">Comprobando Strava...</div>

        <div class="action-row">
          <button class="btn" onclick="connectStrava()">Conectar Strava</button>
        </div>

        <div class="row" style="margin-top:14px">
          <div class="field span-4">
            <label>Desde</label>
            <input id="stravaFrom" type="date" value="${from}">
          </div>
          <div class="field span-4">
            <label>Hasta</label>
            <input id="stravaTo" type="date" value="${to}">
          </div>
          <div class="field span-4">
            <label>&nbsp;</label>
            <button class="btn secondary" onclick="previewStrava()">Buscar actividades</button>
          </div>
        </div>

        <div id="stravaList" style="margin-top:14px"></div>
      </div>

      <div class="card note-box">
        <h3>Privacidad</h3>
        <p>Strava solo se consulta cuando pulsas buscar/importar.</p>
        <p>Los tokens quedan en la Raspberry dentro de data/ y no se suben al repo.</p>
        <p class="muted">Ruta recomendada: Zepp/Amazfit → Strava → Diet Pro Planner.</p>
      </div>
    </div>
  `;

  loadStravaStatus();
}

async function loadStravaStatus(){
  try{
    const s = await api('/api/strava/status');
    $('#stravaStatus').innerHTML = `
      <div class="status ${s.connected ? 'ok' : s.configured ? 'warn' : 'bad'}">
        <b>${s.connected ? 'Conectado' : s.configured ? 'Configurado, falta conectar' : 'No configurado'}</b>
        <span>${s.connected ? 'Listo para buscar actividades por fecha.' : s.message}</span>
      </div>`;
    window.__stravaConnectUrl = s.connect_url;
  }catch(e){
    $('#stravaStatus').textContent = 'No se pudo comprobar Strava: ' + e.message;
  }
}

function connectStrava(){
  if(window.__stravaConnectUrl) window.open(window.__stravaConnectUrl, '_blank');
  else toast('Primero configura Strava en .env');
}

async function previewStrava(){
  const after_date = $('#stravaFrom').value;
  const before_date = $('#stravaTo').value;

  $('#stravaList').innerHTML = '<div class="empty">Buscando actividades en Strava...</div>';

  try{
    const r = await api('/api/strava/preview', {
      method: 'POST',
      body: JSON.stringify({after_date, before_date})
    });
    __stravaPreview = r.activities || [];
    renderStravaPreview();
  }catch(e){
    $('#stravaList').innerHTML = `<div class="empty">Strava: ${e.message}</div>`;
  }
}

function renderStravaPreview(){
  if(!__stravaPreview.length){
    $('#stravaList').innerHTML = '<div class="empty">No hay actividades en ese rango.</div>';
    return;
  }

  $('#stravaList').innerHTML = `
    <div class="section-title compact-title">
      <div>
        <h3>Actividades encontradas</h3>
        <p>${__stravaPreview.length} actividades · selecciona cuáles importar</p>
      </div>
      <button class="btn" onclick="importSelectedStrava()">Importar seleccionadas</button>
    </div>

    <div class="compact-list">
      ${__stravaPreview.map(a => `
        <label class="compact-card workout" style="display:block;cursor:pointer;opacity:${a.already_imported ? .55 : 1}">
          <div class="compact-head">
            <div>
              <b>${a.date} ${a.time} · ${a.sport_type || a.type}</b>
              <small>${a.title} · ${fmt(a.minutes)} min · ${fmt(a.distance_km)} km · ${fmt(a.kcal)} kcal ${a.already_imported ? '· ya importada' : ''}</small>
            </div>
            <input type="checkbox" data-strava-id="${a.id}" ${a.already_imported ? 'disabled' : 'checked'}>
          </div>
        </label>
      `).join('')}
    </div>
  `;
}

async function importSelectedStrava(){
  const ids = [...document.querySelectorAll('[data-strava-id]:checked')].map(x => x.dataset.stravaId);

  if(!ids.length){
    toast('No seleccionaste actividades');
    return;
  }

  try{
    const r = await api('/api/strava/import', {
      method: 'POST',
      body: JSON.stringify({
        after_date: $('#stravaFrom').value,
        before_date: $('#stravaTo').value,
        ids
      })
    });

    toast(`Importadas: ${r.imported} · duplicadas: ${r.skipped}`);
    await load();
    page = 'home';
    renderNav();
    render();
  }catch(e){
    toast('Strava: ' + e.message);
  }
}

// V004_STRAVA_AUTO_SYNC_UI
async function loadStravaAutoStatus(){
  try{
    const s = await api('/api/strava/auto-status');
    const box = $('#stravaAutoStatus');
    if(!box) return;
    const last = s.last_message || 'Aún no sincronizado automáticamente';
    const result = s.last_result || {};
    box.innerHTML = `
      <div class="status ${s.enabled ? 'ok' : 'warn'}">
        <b>${s.enabled ? 'Auto-sync activado' : 'Auto-sync desactivado'}</b>
        <span>${last}</span>
      </div>
      <p class="muted">Último resultado: ${fmt(result.imported||0)} nuevas · ${fmt(result.skipped||0)} duplicadas · ${fmt(result.received||0)} recibidas</p>
    `;
    const enabled = $('#stravaAutoEnabled');
    const interval = $('#stravaAutoInterval');
    const from = $('#stravaAutoFrom');
    if(enabled) enabled.checked = !!s.enabled;
    if(interval) interval.value = s.interval_minutes || 30;
    if(from && !from.value) from.value = s.after_date || s.latest_import_date || today();
  }catch(e){
    const box = $('#stravaAutoStatus');
    if(box) box.innerHTML = `<div class="empty">Auto-sync: ${e.message}</div>`;
  }
}

async function saveStravaAutoConfig(){
  try{
    const r = await api('/api/strava/auto-config', {
      method: 'POST',
      body: JSON.stringify({
        enabled: $('#stravaAutoEnabled').checked,
        after_date: $('#stravaAutoFrom').value,
        interval_minutes: $('#stravaAutoInterval').value
      })
    });
    toast(r.last_message || 'Auto-sync guardado');
    await loadStravaAutoStatus();
  }catch(e){ toast('Auto-sync: ' + e.message); }
}

async function runStravaAutoNow(){
  const box = $('#stravaAutoStatus');
  if(box) box.innerHTML = '<div class="empty">Sincronizando ahora...</div>';
  try{
    const r = await api('/api/strava/auto-run', {method:'POST', body: JSON.stringify({})});
    toast(r.message || `Importadas: ${r.imported}`);
    await load();
    page = 'integrations';
    renderNav();
    render();
  }catch(e){
    toast('Auto-sync: ' + e.message);
    await loadStravaAutoStatus();
  }
}

function renderIntegrations(){
  const to = today();
  const from = localStorage.getItem('stravaDefaultFrom') || new Date(Date.now() - 14 * 86400000).toISOString().slice(0,10);
  const autoPreview = localStorage.getItem('stravaAutoPreview') === '1';

  $('#view').innerHTML = `
    <div class="grid cols-2">
      <div class="card integration-card">
        <h3>🔗 Strava</h3>
        <p class="muted">Conecta Strava, elige fechas, revisa actividades e importa solo las que marques.</p>
        <div id="stravaStatus" class="empty">Comprobando Strava...</div>
        <div class="action-row"><button class="btn" onclick="connectStrava()">Conectar Strava</button></div>
        <div class="row" style="margin-top:14px">
          <div class="field span-4"><label>Desde</label><input id="stravaFrom" type="date" value="${from}" onchange="localStorage.setItem('stravaDefaultFrom',this.value)"></div>
          <div class="field span-4"><label>Hasta</label><input id="stravaTo" type="date" value="${to}"></div>
          <div class="field span-4"><label>&nbsp;</label><button class="btn secondary" onclick="previewStrava()">Buscar actividades</button></div>
        </div>
        <label class="check-line"><input id="autoPreviewCheck" type="checkbox" ${autoPreview?'checked':''} onchange="localStorage.setItem('stravaAutoPreview',this.checked?'1':'0')"> Cargar la lista automáticamente al abrir esta página</label>
        <div id="stravaList" style="margin-top:14px"></div>
      </div>

      <div class="card note-box">
        <h3>⚙️ Auto-sync en segundo plano</h3>
        <p>Importa nuevas actividades de Strava sin abrir la página. La Raspberry revisa Strava cada cierto tiempo.</p>
        <div id="stravaAutoStatus" class="empty">Comprobando auto-sync...</div>
        <div class="row" style="margin-top:12px">
          <div class="field span-5"><label>Importar desde</label><input id="stravaAutoFrom" type="date" value="${from}"></div>
          <div class="field span-4"><label>Cada</label><select id="stravaAutoInterval"><option value="15">15 min</option><option value="30" selected>30 min</option><option value="60">1 hora</option><option value="180">3 horas</option></select></div>
          <div class="field span-3"><label>&nbsp;</label><button class="btn secondary" onclick="runStravaAutoNow()">Sincronizar ahora</button></div>
        </div>
        <label class="check-line"><input id="stravaAutoEnabled" type="checkbox"> Sincronizar automáticamente nuevas actividades</label>
        <div class="action-row"><button class="btn" onclick="saveStravaAutoConfig()">Guardar auto-sync</button></div>
        <p class="muted">Sincronizado correctamente a fecha aparecerá arriba cuando termine cada revisión. No sube tokens ni datos al repo.</p>
      </div>
    </div>
  `;

  loadStravaStatus();
  loadStravaAutoStatus().then(()=>{ if(autoPreview) previewStrava(); });
}


// V006_STABLE_ES_FIXES
(function(){
  // Spanish-only stable UI. Full i18n needs a key-based refactor, not DOM text replacement.
  function stableHeader(){
    document.documentElement.lang = 'es';
    document.documentElement.dataset.lang = 'es';
    document.title = 'Diet Pro Planner · v0.0.19';
    const brand = document.querySelector('.brand h1');
    if(brand) brand.textContent = 'Diet Pro Planner';
    const sub = document.querySelector('.brand p');
    if(sub) sub.textContent = 'Raspberry · local · privado';
    const eyebrow = document.querySelector('.eyebrow');
    if(eyebrow) eyebrow.textContent = 'Dieta controlada · v0.0.19';
    const lang = document.querySelector('#btnLang');
    if(lang) lang.remove();
  }

  const oldRender = window.render || render;
  window.render = function(){
    oldRender();
    stableHeader();
  };

  const oldRenderNav = window.renderNav || renderNav;
  window.renderNav = function(){
    oldRenderNav();
    stableHeader();
  };

  // Make sure numeric totals stay numeric even after older cached language state.
  const oldRenderHome = window.renderHome || renderHome;
  window.renderHome = function(){
    oldRenderHome();
    stableHeader();
    const metrics = document.querySelectorAll('.metric');
    // If an older broken translation left text like "Home,Resumen" in the activity metric, force rerender by data.
    try{
      const workouts = byDate(state.workouts);
      const sport = workoutTotals(workouts);
      const cards = [...document.querySelectorAll('.metric')];
      const activity = cards.find(c => /Actividad/.test(c.textContent));
      if(activity){
        const b = activity.querySelector('b');
        if(b) b.textContent = fmt(sport);
      }
    }catch(e){}
  };

  stableHeader();
})();

















/* DPP_UI5_FULL_REDESIGN_START */
const UI5_NAV={home:['🏠','Resumen','Panel diario'],register:['🍽️','Registrar','Comidas'],sport:['🏋️','Deporte','Strava/manual'],templates:['⚡','Plantillas','2 clics'],foods:['🥫','Alimentos','Productos/OCR'],plan:['📅','Plan','Semana'],weights:['⚖️','Peso','Historial'],integrations:['🔗','Integraciones','Strava'],history:['📚','Historial','Todo']};
function renderNav(){const nav=$('#nav'); if(!nav)return; nav.innerHTML=PAGES.map(([id,ico,label])=>{const p=UI5_NAV[id]||[ico,label,''];return `<button class="${page===id?'active':''}" data-page="${id}"><span class="nav-ico">${p[0]}</span><span class="nav-copy"><b>${p[1]}</b><small>${p[2]}</small></span></button>`}).join('');document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{page=b.dataset.page;renderNav();render()})}
function ui5OfficialWeights(){return state.weights.filter(w=>w.official).sort((a,b)=>(a.date+a.time).localeCompare(b.date+b.time))}
function ui5Trend(){const ws=ui5OfficialWeights(); if(ws.length<2)return{label:'Sin tendencia',cls:'neutral',text:'Registra 2+ pesos oficiales de mañana.'}; const f=ws[0],l=ws.at(-1),days=Math.max(1,(new Date(l.date)-new Date(f.date))/(1000*3600*24)),delta=Number(l.kg)-Number(f.kg); if(days<7||ws.length<5)return{label:delta<0?'Bajada inicial':delta>0?'Subida inicial':'Estable',cls:'info',text:`${fmt(delta)} kg desde ${f.date}. Pocos días: sin extrapolar kg/semana.`}; const weekly=delta/days*7; if(weekly<-1)return{label:'Bajada rápida',cls:'warn',text:`${fmt(delta)} kg · ${fmt(weekly)} kg/sem aprox.`}; if(weekly<-0.35)return{label:'Bajada correcta',cls:'good',text:`${fmt(delta)} kg · ${fmt(weekly)} kg/sem aprox.`}; if(delta>0)return{label:'Subiendo',cls:'bad',text:`${fmt(delta)} kg · ${fmt(weekly)} kg/sem aprox.`}; return{label:'Estable',cls:'info',text:`${fmt(delta)} kg · ${fmt(weekly)} kg/sem aprox.`}}
function weightChart(){const ws=ui5OfficialWeights().slice(-14); if(ws.length<2)return '<div class="empty">Cuando tengas 2+ pesos oficiales aparece la gráfica.</div>'; const vals=ws.map(w=>Number(w.kg)),min=Math.min(...vals)-.25,max=Math.max(...vals)+.25,W=640,H=280,L=68,R=32,T=42,B=56,pw=W-L-R,ph=H-T-B,x=i=>L+(ws.length===1?0:i*(pw/(ws.length-1))),y=v=>T+(max-v)/(max-min)*ph,pts=ws.map((w,i)=>`${x(i)},${y(Number(w.kg))}`).join(' '); const ticks=[min,(min+max)/2,max].map(v=>`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" stroke="rgba(31,60,90,.13)"/><text x="14" y="${y(v)+5}" font-size="13" font-weight="800" fill="#314964">${fmt(v)}</text>`).join(''); const dots=ws.map((w,i)=>`<g><circle cx="${x(i)}" cy="${y(Number(w.kg))}" r="7" fill="#2563eb" stroke="#fff" stroke-width="3"/><text x="${x(i)}" y="${y(Number(w.kg))-14}" text-anchor="middle" font-size="13" font-weight="900" fill="#0b1726">${fmt(w.kg)}</text><title>${w.date} ${w.time}: ${fmt(w.kg)} kg</title></g>`).join(''); const tr=ui5Trend(); return `<div class="ui5-chartbox"><svg class="chart ui5-weight-chart" viewBox="0 0 ${W} ${H}">${ticks}<polyline points="${pts}" fill="none" stroke="#2563eb" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>${dots}<text x="${L}" y="${H-18}" font-size="13" font-weight="800" fill="#54677f">${ws[0].date}</text><text x="${W-R}" y="${H-18}" text-anchor="end" font-size="13" font-weight="800" fill="#54677f">${ws.at(-1).date}</text></svg><div class="ui5-trend"><span class="ui5-chip ${tr.cls}">${tr.label}</span><b>${tr.text}</b></div></div>`}
function assistantFor(d=day()){const meals=byDate(state.meals,d),workouts=byDate(state.workouts,d),mt=mealTotals(meals),sport=workoutTotals(workouts),lw=latestWeight(),tr=ui5Trend(),names=meals.flatMap(m=>[m.name,m.notes||'',...(m.items||[]).map(i=>i.food_name)]).join(' ').toLowerCase(),tips=[]; if(!lw)tips.push('Registra peso oficial de mañana para construir tendencia real.'); else if(!lw.official)tips.push('Último peso es referencia; para tendencia usa mañana, después de baño y antes de desayunar.'); else tips.push(`Peso oficial: ${fmt(lw.kg)} kg. ${tr.text}`); if(mt.protein<80)tips.push('Proteína baja: prioriza pollo, huevos, atún, yogur proteico, jamón cocido extra o queso fresco batido.'); else if(mt.protein<120)tips.push('Proteína aceptable: intenta cerrar cerca de 130 g.'); else tips.push('Proteína bien cubierta hoy.'); if(mt.kcal<900)tips.push('Comida registrada baja: planifica comida/cena para no llegar con ansiedad.'); else if(mt.kcal>2300)tips.push('Kcal altas: siguiente comida limpia, sin dulce ni pan/arroz extra.'); else tips.push('Balance razonable: controla aceite y raciones.'); if(mt.oil>10)tips.push('Aceite alto: siguiente comida con sartén antiadherente y 0–5 g.'); if(sport>=900)tips.push('Mucho deporte: carbohidrato controlado sí, barra libre no.'); else if(sport>=300)tips.push('Buen gasto de actividad: recupera con proteína, no con picoteo.'); if(/chocolate|galleta|piruleta|dulce|tirma/.test(names))tips.push('Hubo dulce/snack: cierra con proteína + verdura.'); return [...new Set(tips)].slice(0,6)}
function ui5Progress(label,value,pct,sub,tone='good'){return `<article class="ui5-progress ${tone}"><div><span>${label}</span><b>${value}</b></div><i><em style="width:${Math.max(4,Math.min(100,pct))}%"></em></i><small>${sub}</small></article>`}
function quickActions(){return `<section class="quick-actions ui5-actions"><button class="quick primary" onclick="go('register')"><span>🍽️</span><b>Comida</b><small>alimentos + gramos</small></button><button class="quick sport" onclick="go('sport')"><span>🏋️</span><b>Entreno</b><small>Strava/manual</small></button><button class="quick weight" onclick="go('weights')"><span>⚖️</span><b>Peso</b><small>oficial/referencia</small></button><button class="quick" onclick="go('templates')"><span>⚡</span><b>Plantilla</b><small>cambia gramos</small></button><button class="quick help-tile" onclick="openHelpModal()"><span>❔</span><b>Ayuda</b><small>guía rápida</small></button></section>`}
function renderHome(){const lw=latestWeight(),meals=byDate(state.meals),workouts=byDate(state.workouts),mt=mealTotals(meals),sport=workoutTotals(workouts),protTarget=135,kcalTarget=Math.max(1500,1900+Math.min(sport,900)*.35),tr=ui5Trend(); $('#view').innerHTML=`<section class="ui5-hero"><div class="ui5-hero-copy"><span class="ui5-kicker">Diet Pro Planner · local</span><h2>Panel diario para comer, entrenar y ajustar sin perder tiempo.</h2><p>Comidas por gramos, peso oficial, OCR de etiquetas, Strava y asistente en una vista clara.</p><div class="ui5-pills"><span><small>Peso</small><b>${lw?fmt(lw.kg)+' kg':'—'}</b></span><span><small>Proteína</small><b>${fmt(mt.protein)} / ${protTarget} g</b></span><span><small>Actividad</small><b>${fmt(sport)} kcal</b></span><span><small>Tendencia</small><b>${tr.label}</b></span></div></div><div class="ui5-hero-panel">${ui5Progress('Proteína',fmt(mt.protein)+' g',mt.protein/protTarget*100,'Objetivo 130–150 g',mt.protein>=120?'good':'warn')}${ui5Progress('Comida',fmt(mt.kcal)+' kcal',mt.kcal/kcalTarget*100,'Objetivo flexible '+fmt(kcalTarget)+' kcal aprox.',mt.kcal>2300?'bad':'good')}${ui5Progress('Actividad',fmt(sport)+' kcal',Math.min(100,sport/10),sport?'Actividad registrada':'Sin entrenos hoy',sport>900?'warn':'good')}</div></section>${quickActions()}${dateBar()}<div class="grid cols-4 dashboard-metrics">${metric('⚖️','Último peso',lw?`${fmt(lw.kg)} kg`:'—',lw?`${lw.date} ${lw.time} · ${lw.official?'oficial':'referencia'}`:'sin datos')}${metric('🍽️','Comido',fmt(mt.kcal),'kcal estimadas')}${metric('💪','Proteína',`${fmt(mt.protein)} g`,'objetivo 130–150 g')}${metric('🔥','Actividad',fmt(sport),'kcal del día seleccionado')}</div><div class="grid cols-2 home-main" style="margin-top:14px"><div class="card assistant compact-assistant"><h3>🤖 Asistente</h3><ul>${assistantFor().map(x=>`<li>${x}</li>`).join('')}</ul></div><div class="card"><h3>📉 Peso oficial</h3>${weightChart()}<p class="muted">Solo pesos oficiales de mañana. Con pocos días no extrapolamos kg/semana.</p></div></div><div class="day-columns"><section class="card day-panel"><div class="section-title compact-title"><div><h3>🍽️ Comidas</h3><p>${fmt(mt.kcal)} kcal · ${fmt(mt.protein)} g prot.</p></div><button class="btn small" onclick="go('register')">+ Comida</button></div><div class="compact-list">${meals.length?meals.map(mealCardCompact).join(''):'<div class="empty">Sin comidas.</div>'}</div></section><section class="card day-panel"><div class="section-title compact-title"><div><h3>🏋️ Actividad</h3><p>${fmt(sport)} kcal</p></div><button class="btn small" onclick="go('sport')">+ Entreno</button></div><div class="compact-list">${workouts.length?workouts.map(workoutCardCompact).join(''):'<div class="empty">Sin entrenos para este día.</div>'}</div></section></div><div class="footer-space"></div>`}
function ui5ApplyShell(){document.documentElement.dataset.ui='ui5'; const e=document.querySelector('.eyebrow'); if(e)e.textContent='Dieta controlada · v0.0.19'; const r=document.querySelector('.rule-banner'); if(r&&r.dataset.ui5!=='1'){r.dataset.ui5='1';r.innerHTML=`<article class="ui5-rule protein"><span>Proteína</span><b>130–150 g/día</b><small>Prioridad antes de recortar de más.</small></article><article class="ui5-rule oil"><span>Aceite</span><b>5 g normal · 10 g máximo</b><small>Medido, no a ojo.</small></article><article class="ui5-rule carbs"><span>Pasta/arroz</span><b>Pesar en seco</b><small>Ración según deporte y hambre real.</small></article>`} const sr=document.querySelector('.sidebar .side-rule'); if(sr&&sr.dataset.ui5!=='1'){sr.dataset.ui5='1';sr.innerHTML='<span>Regla rápida</span><b>Proteína + aceite medido</b><small>Pasta/arroz en seco · dulces controlados.</small>'} if(!document.getElementById('ui5Badge')){const b=document.createElement('div');b.id='ui5Badge';b.className='ui5-badge';b.textContent='v0.0.19';document.querySelector('.topbar')?.appendChild(b)} if(!document.getElementById('floatingHelp')){const h=document.createElement('button');h.id='floatingHelp';h.className='floating-help';h.textContent='?';h.onclick=openHelpModal;h.title='Ayuda';document.body.appendChild(h)}}
function openHelpModal(){closeHelpModal(); const o=document.createElement('div');o.id='helpOverlay';o.className='help-overlay';o.innerHTML=`<div class="help-modal"><button class="help-close" onclick="closeHelpModal()">×</button><span class="ui5-kicker">Ayuda rápida</span><h2>Diet Pro Planner</h2><div class="help-grid"><div><b>🍽️ Comidas</b><p>Usa plantillas, cambia gramos y guarda. Pasta/arroz siempre en seco.</p></div><div><b>⚖️ Peso</b><p>Oficial por la mañana. Post-comida, noche o post-entreno son referencia.</p></div><div><b>📷 OCR</b><p>Sube foto de etiqueta. Tesseract intenta leerla. Revisa valores antes de guardar.</p></div><div><b>🏋️ Strava</b><p>Importa por ID y evita duplicados. Auto-sync queda igual.</p></div><div><b>🤖 Asistente</b><p>Consejos por proteína, kcal, aceite, deporte y dulces.</p></div><div><b>🔐 Privacidad</b><p>Esta prueba es local. No sube DB, tokens, .env ni fotos al repo.</p></div></div><div class="help-actions"><button class="btn" onclick="closeHelpModal();go('register')">Registrar comida</button><button class="btn secondary" onclick="closeHelpModal();go('foods')">Alimentos/OCR</button><button class="btn secondary" onclick="closeHelpModal();go('weights')">Peso</button></div></div>`;o.onclick=e=>{if(e.target.id==='helpOverlay')closeHelpModal()};document.body.appendChild(o)}
function closeHelpModal(){document.getElementById('helpOverlay')?.remove()}
if(!window.__DPP_UI5_PATCHED__){window.__DPP_UI5_PATCHED__=true; const prev=render; render=function(){prev();setTimeout(ui5ApplyShell,0)}; window.addEventListener('DOMContentLoaded',()=>setTimeout(ui5ApplyShell,0)); setTimeout(()=>{try{renderNav();render();ui5ApplyShell()}catch(e){console.error(e)}},250); setInterval(ui5ApplyShell,3000)}
/* DPP_UI5_FULL_REDESIGN_END */






/* DPP_OCR3_FRONTEND_START */
/* OCR3 frontend: faster feedback, exact known label support, concise source notes. */

function ocr3Set(id, val){
  const el=document.querySelector(id);
  if(!el || val===undefined || val===null || val==='') return;
  el.value=String(val).replace(',', '.');
}
function ocr3Badge(text, cls='info'){
  return `<span class="ocr3-badge ${cls}">${text}</span>`;
}
async function uploadFoodPhoto(){
  const file=document.querySelector('#fPhoto')?.files?.[0];
  if(!file) return;

  const preview=document.querySelector('#photoPreview');
  if(preview) preview.innerHTML=`${ocr3Badge('leyendo OCR...', 'info')}`;

  const form=new FormData();
  form.append('photo', file);

  try{
    const r=await apiForm('/api/food-photo-ocr', form);
    selectedFoodPhoto=r.photo_path;

    const n=r.nutrition||{};
    const product=r.product||{};
    const serving=r.serving||{};
    const extra=r.extra||{};
    const warnings=r.warnings||[];
    const conf=r.confidence||'baja';

    const nameEl=document.querySelector('#fName');
    const brandEl=document.querySelector('#fBrand');
    if(nameEl && product.name) nameEl.value=product.name;
    if(brandEl && product.brand) brandEl.value=product.brand;

    ocr3Set('#fKcal', n.kcal);
    ocr3Set('#fProt', n.protein);
    ocr3Set('#fCarbs', n.carbs);
    ocr3Set('#fFat', n.fat);
    ocr3Set('#fSugar', n.sugar);
    ocr3Set('#fSalt', n.salt);
    ocr3Set('#fTypical', n.typical_g || product.typical_g || serving.grams);

    const sourceParts=[];
    sourceParts.push(`OCR ${r.ocr_engine||'local'} · modo ${r.ocr_mode||'-'} · confianza ${conf}${r.cache_hit?' · cache':''}.`);
    if(product.name) sourceParts.push(`Producto: ${product.name}${product.brand?' · '+product.brand:''}.`);
    if(serving.grams){
      sourceParts.push(`Ración etiqueta ${serving.grams} g: ${serving.kcal??'-'} kcal · ${serving.protein??'-'} g prot · ${serving.fat??'-'} g grasa · ${serving.salt??'-'} g sal.`);
    }
    if(extra.saturated!==undefined || extra.calcium_mg!==undefined){
      sourceParts.push(`Extra por 100 g: saturadas ${extra.saturated??'-'} g · calcio ${extra.calcium_mg??'-'} mg.`);
    }
    if(warnings.length) sourceParts.push(`Avisos: ${warnings.slice(0,5).join(' | ')}`);
    if(r.ocr_text) sourceParts.push((r.ocr_text.length>650?r.ocr_text.slice(0,650)+'…':r.ocr_text));

    const source=document.querySelector('#fSource');
    if(source) source.value=sourceParts.join('\n\n');

    if(preview){
      const fields=Object.keys(n).join(', ') || 'sin valores seguros';
      const cls=conf==='alta'?'good':conf==='media'?'info':conf==='baja'?'warn':'bad';
      preview.innerHTML=`
        <img class="food-photo preview" src="${selectedFoodPhoto}" alt="foto etiqueta">
        <div class="ocr3-status">
          ${ocr3Badge('foto guardada','good')}
          ${ocr3Badge(r.cache_hit?'OCR desde cache':'OCR leído','good')}
          ${ocr3Badge('confianza '+conf,cls)}
          <small>Campos: ${fields}</small>
          ${warnings[0]?`<small class="ocr3-warn">${warnings[0]}</small>`:''}
        </div>
      `;
    }
    toast(r.cache_hit?'OCR desde cache: revisa y guarda':'OCR leído: revisa y guarda');
  }catch(e){
    if(preview) preview.innerHTML=ocr3Badge('error OCR','bad');
    toast(e.message || 'Error OCR');
  }
}
/* DPP_OCR3_FRONTEND_END */


/* DPP_UI5_PLAN_SPORT_START */
/* Plan and sport layout: less vertical, more dashboard-like. */

function ui5WorkoutDateLabel(w){
  return `${w.date||''} · ${w.time||''}`;
}
function ui5SportCard(w){
  const kcal = Number(w.kcal||0);
  const km = Number(w.distance_km||0);
  const min = Number(w.minutes||0);
  return `<article class="ui5-sport-card">
    <div class="ui5-sport-head">
      <div><b>${w.name||'Entreno'}</b><small>${ui5WorkoutDateLabel(w)}</small></div>
      <button class="btn small danger" onclick="deleteWorkout(${w.id})">×</button>
    </div>
    <div class="ui5-sport-metrics">
      <span><b>${fmt(min)}</b><small>min</small></span>
      <span><b>${fmt(km)}</b><small>km</small></span>
      <span><b>${fmt(kcal)}</b><small>kcal</small></span>
    </div>
    <p>${w.notes||''}</p>
  </article>`;
}

function renderSport(){
  const all=[...state.workouts].sort((a,b)=>(b.date+b.time).localeCompare(a.date+a.time));
  const last7=all.filter(w=>{
    try{return (Date.now()-new Date(w.date+'T12:00:00').getTime()) <= 7*86400000;}catch{return false}
  });
  const totalKcal=last7.reduce((a,w)=>a+Number(w.kcal||0),0);
  const totalMin=last7.reduce((a,w)=>a+Number(w.minutes||0),0);
  const totalKm=last7.reduce((a,w)=>a+Number(w.distance_km||0),0);

  $('#view').innerHTML=`
    <section class="ui5-sport-hero">
      <div><span class="ui5-kicker">Deporte</span><h3>Registrar o revisar actividad</h3><p>Strava queda como fuente principal; el manual sirve para ajustes rápidos.</p></div>
      <div class="ui5-sport-summary">
        <span><b>${fmt(totalKcal)}</b><small>kcal 7 días</small></span>
        <span><b>${fmt(totalMin)}</b><small>min 7 días</small></span>
        <span><b>${fmt(totalKm)}</b><small>km 7 días</small></span>
      </div>
    </section>

    <div class="ui5-sport-layout">
      <div class="card ui5-sport-form">
        <h3>🏋️ Nuevo entreno</h3>
        <div class="row compact-row">
          <div class="field span-3"><label>Fecha</label><input id="sDate" type="date" value="${today()}"></div>
          <div class="field span-2"><label>Hora</label><input id="sTime" type="time" value="${nowHM()}"></div>
          <div class="field span-4"><label>Ejercicio</label><select id="sName">${state.exercises.map(e=>`<option>${e.name}</option>`).join('')}</select></div>
          <div class="field span-3"><label>Minutos</label><input id="sMin" type="number" inputmode="decimal"></div>
          <div class="field span-3"><label>Distancia km</label><input id="sKm" type="number" step="0.01" inputmode="decimal"></div>
          <div class="field span-3"><label>Calorías reloj</label><input id="sKcal" type="number" placeholder="vacío = estima"></div>
          <div class="field span-6"><label>Notas</label><input id="sNotes" placeholder="Strava, reloj, sensación, etc."></div>
          <div class="field span-3"><label>&nbsp;</label><button class="btn" onclick="saveWorkout()">Guardar entreno</button></div>
        </div>
      </div>

      <div class="card ui5-exercise-form">
        <h3>➕ Tipo ejercicio</h3>
        <p class="muted">Añade solo si falta un tipo manual. Para Strava no hace falta.</p>
        <div class="row compact-row">
          <div class="field span-6"><label>Nombre</label><input id="eName" placeholder="Ej. Caminata suave"></div>
          <div class="field span-3"><label>MET</label><input id="eMet" type="number" value="5"></div>
          <div class="field span-3"><label>&nbsp;</label><button class="btn secondary" onclick="saveExercise()">Guardar</button></div>
          <div class="field span-12"><label>Notas</label><input id="eNotes"></div>
        </div>
      </div>
    </div>

    <div class="section-title ui5-section-title"><div><h3>Historial deporte</h3><p>${all.length} entrenos · últimos primero</p></div></div>
    <div class="ui5-sport-history">${all.map(ui5SportCard).join('')}</div>
  `;
}

function ui5MealLine(label, value){
  return value ? `<p><b>${label}</b><span>${value}</span></p>` : '';
}
function ui5PlanDayCard(d, idx){
  return `<article class="ui5-plan-day">
    <div class="ui5-plan-day-head"><span>${idx+1}</span><b>${d.day||'Día'}</b></div>
    ${ui5MealLine('Desayuno', d.breakfast)}
    ${ui5MealLine('Comida', d.lunch)}
    ${ui5MealLine('Merienda', d.snack)}
    ${ui5MealLine('Cena', d.dinner)}
  </article>`;
}
function renderPlanPayload(p){
  const days=p.days||[];
  return `<div class="ui5-plan-current">
    <div class="ui5-plan-intro">
      <span class="ui5-kicker">Plan actual</span>
      <h3>${p.name||'Plan semanal'}</h3>
      <p>${p.notes||'Sin notas.'}</p>
    </div>
    <div class="ui5-plan-days">${days.map(ui5PlanDayCard).join('')}</div>
  </div>`;
}
function renderPlan(){
  const p=state.plans[0]?JSON.parse(state.plans[0].payload):null;
  $('#view').innerHTML=`
    <div class="ui5-plan-layout">
      <section class="card ui5-plan-import">
        <h3>📥 Importar plan</h3>
        <p class="muted">Pega JSON semanal. El plan se muestra en tarjetas horizontales.</p>
        <textarea id="planRaw" placeholder='{"name":"Semana...","days":[...]}'></textarea>
        <button class="btn" onclick="savePlan()">Importar plan</button>
      </section>
      <section class="card ui5-plan-board">
        ${p?renderPlanPayload(p):'<div class="empty">Sin plan.</div>'}
      </section>
    </div>`;
}
/* DPP_UI5_PLAN_SPORT_END */









/* DPP_UI5_PLAN_EDITOR_START */
/* Plan editor v2 local-only.
   Fixes missing escapeHtml, broken plan parsing, and blank Plan page.
   No repo push, no DB schema change, keeps existing /api/plans endpoint. */

function ui5Esc(v){
  return String(v ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#39;'
  }[c]));
}

function ui5SafePlanPayload(raw){
  if(!raw) return null;
  try{
    if(typeof raw === 'string') return JSON.parse(raw);
    if(typeof raw === 'object') return raw;
  }catch(e){
    console.warn('Plan JSON inválido', e, raw);
  }
  return null;
}

function ui5PlanDefaultWeek(){
  return {
    name: "Semana dieta controlada · editable",
    notes: "Plan local editable. Proteína 130–150 g/día, aceite medido, pasta/arroz en seco. Ajustar según deporte y hambre real.",
    days: [
      {
        day: "Viernes · hoy",
        breakfast: "Tostada 42 g + café con edulcorante + yogur proteico 120 g.",
        lunch: "80 g pasta seca + pollo 200–224 g crudo + verdura/judía verde. Aceite 5 g.",
        snack: "Si hay 12K/andaina: plátano o 2–3 tortitas + agua. Si no hay deporte: yogur proteico o fruta.",
        dinner: "Cena limpia: 2 huevos + jamón cocido extra 70–90 g + judía verde 250 g. Queso curado 10–15 g opcional.",
        target: "130–150 g proteína · aceite 5–10 g",
        status: "planificado"
      },
      {
        day: "Sábado",
        breakfast: "Tostada + café + yogur proteico.",
        lunch: "Proteína principal + verdura + arroz/pasta solo si hay actividad.",
        snack: "Fruta + yogur proteico. Gelatina 0 si hay antojo.",
        dinner: "Proteína + verdura. Evitar dulce nocturno.",
        target: "déficit controlado",
        status: "borrador"
      },
      {
        day: "Domingo",
        breakfast: "Desayuno base: tostada + café + yogur proteico.",
        lunch: "Comida flexible: prioriza proteína y mide pan/arroz/pasta.",
        snack: "Yogur proteico o fruta.",
        dinner: "Pescado/huevos/atún + verdura.",
        target: "cerrar semana limpio",
        status: "borrador"
      },
      {
        day: "Lunes",
        breakfast: "Tostada + café + yogur proteico.",
        lunch: "Tupper: carbo pesado en seco + pollo/atún + verdura + 5 g aceite.",
        snack: "Queso fresco batido o yogur proteico.",
        dinner: "Huevo entero/pescado + verdura.",
        target: "rutina",
        status: "borrador"
      }
    ]
  };
}

function ui5PlanNormalize(p){
  p = p || {};
  if(!Array.isArray(p.days)) p.days = [];
  return {
    name: p.name || "Plan semanal",
    notes: p.notes || "",
    days: p.days.map(d => ({
      day: d.day || "",
      breakfast: d.breakfast || "",
      lunch: d.lunch || "",
      snack: d.snack || "",
      dinner: d.dinner || "",
      target: d.target || "",
      status: d.status || "borrador"
    }))
  };
}

function ui5CurrentPlan(){
  try{
    const row = state.plans && state.plans.length ? state.plans[0] : null;
    const parsed = row ? ui5SafePlanPayload(row.payload) : null;
    return ui5PlanNormalize(parsed || ui5PlanDefaultWeek());
  }catch(e){
    console.error('Error cargando plan', e);
    return ui5PlanNormalize(ui5PlanDefaultWeek());
  }
}

function ui5PlanStats(p){
  const days = p.days || [];
  const planned = days.filter(d => [d.breakfast,d.lunch,d.snack,d.dinner].some(x => String(x||'').trim())).length;
  return {days: days.length, planned, missing: Math.max(0, 7 - days.length)};
}

function ui5PlanDayHtml(d, idx){
  const status = d.status || "borrador";
  return `<article class="ui5-edit-day" data-plan-day="${idx}">
    <header>
      <span>${idx+1}</span>
      <div>
        <input class="ui5-day-title" data-plan-field="day" value="${ui5Esc(d.day)}" placeholder="Ej. Viernes · recuperación">
        <select data-plan-field="status">
          ${["planificado","pendiente ajustar","borrador","realizado"].map(x => `<option value="${ui5Esc(x)}" ${x===status?'selected':''}>${ui5Esc(x)}</option>`).join('')}
        </select>
      </div>
      <button class="btn small danger" onclick="ui5DeletePlanDay(${idx})">×</button>
    </header>
    <label><b>Desayuno</b><textarea data-plan-field="breakfast" placeholder="Tostada + yogur...">${ui5Esc(d.breakfast)}</textarea></label>
    <label><b>Comida</b><textarea data-plan-field="lunch" placeholder="Tupper, pasta/arroz, proteína...">${ui5Esc(d.lunch)}</textarea></label>
    <label><b>Merienda</b><textarea data-plan-field="snack" placeholder="Fruta, yogur, pre-entreno...">${ui5Esc(d.snack)}</textarea></label>
    <label><b>Cena</b><textarea data-plan-field="dinner" placeholder="Proteína + verdura...">${ui5Esc(d.dinner)}</textarea></label>
    <label><b>Objetivo</b><input data-plan-field="target" value="${ui5Esc(d.target)}" placeholder="130–150 g proteína / aceite 5 g"></label>
  </article>`;
}

function ui5ReadPlanFromDom(){
  const p = {
    name: document.querySelector('#planName')?.value || "Plan semanal",
    notes: document.querySelector('#planNotes')?.value || "",
    days: []
  };
  document.querySelectorAll('[data-plan-day]').forEach(card => {
    const d = {};
    card.querySelectorAll('[data-plan-field]').forEach(el => {
      d[el.dataset.planField] = el.value || "";
    });
    p.days.push(d);
  });
  return ui5PlanNormalize(p);
}

function ui5RefreshPlanStats(p){
  p = p || ui5ReadPlanFromDom();
  const st = ui5PlanStats(p);
  const el = document.querySelector('#ui5PlanStats');
  if(el) el.innerHTML = `
    <span><b>${st.days}</b><small>días</small></span>
    <span><b>${st.planned}</b><small>con comidas</small></span>
    <span><b>${st.missing}</b><small>faltan</small></span>`;
}

function ui5RenderPlanBoard(p){
  const board = document.querySelector('#ui5PlanBoard');
  if(!board) return;
  board.innerHTML = (p.days||[]).map(ui5PlanDayHtml).join('');
  ui5RefreshPlanStats(p);
}

function ui5AddPlanDay(){
  const p = ui5ReadPlanFromDom();
  p.days.push({day:"Nuevo día", breakfast:"", lunch:"", snack:"", dinner:"", target:"130–150 g proteína", status:"borrador"});
  ui5RenderPlanBoard(p);
}

function ui5DeletePlanDay(idx){
  const p = ui5ReadPlanFromDom();
  p.days.splice(idx,1);
  ui5RenderPlanBoard(p);
}

function ui5CompletePlanWeek(){
  const p = ui5ReadPlanFromDom();
  while(p.days.length < 7){
    const n = p.days.length + 1;
    p.days.push({
      day: `Día ${n}`,
      breakfast: "Desayuno base: tostada + café + yogur proteico.",
      lunch: "Proteína + carbo pesado en seco si toca + verdura.",
      snack: "Fruta o yogur proteico.",
      dinner: "Proteína + verdura. Aceite medido.",
      target: "ajustar según actividad",
      status: "borrador"
    });
  }
  ui5RenderPlanBoard(p);
  toast("Semana completada en borrador");
}

function ui5ApplyDefaultPlan(){
  const p = ui5PlanDefaultWeek();
  const n = document.querySelector('#planName');
  const notes = document.querySelector('#planNotes');
  if(n) n.value = p.name;
  if(notes) notes.value = p.notes;
  ui5RenderPlanBoard(p);
  toast("Plan base cargado");
}

async function ui5SaveEditablePlan(){
  const p = ui5ReadPlanFromDom();
  await api('/api/plans', {method:'POST', body: JSON.stringify({raw: JSON.stringify(p, null, 2)})});
  toast("Plan guardado");
  await load();
  page='plan';
  renderNav();
  render();
}

function ui5ExportPlanJson(){
  const p = ui5ReadPlanFromDom();
  const raw = JSON.stringify(p, null, 2);
  const box = document.querySelector('#planRaw');
  if(box) box.value = raw;
  navigator.clipboard?.writeText(raw).then(()=>toast("JSON copiado")).catch(()=>toast("JSON listo abajo"));
}

function renderPlan(){
  let p;
  try{
    p = ui5CurrentPlan();
  }catch(e){
    console.error(e);
    p = ui5PlanNormalize(ui5PlanDefaultWeek());
  }
  const st = ui5PlanStats(p);
  $('#view').innerHTML = `
    <section class="ui5-plan-hero2">
      <div>
        <span class="ui5-kicker">Plan semanal previsto</span>
        <h3>Plan previsto editable. El real registrado se consulta en Historial.</h3>
        <p>Si el plan anterior venía roto, pulsa “Cargar plan base” o “Completar semana”.</p>
      </div>
      <div id="ui5PlanStats" class="ui5-plan-stats">
        <span><b>${st.days}</b><small>días</small></span>
        <span><b>${st.planned}</b><small>con comidas</small></span>
        <span><b>${st.missing}</b><small>faltan</small></span>
      </div>
    </section>

    <section class="card ui5-plan-toolbar">
      <div class="row compact-row">
        <div class="field span-5"><label>Nombre del plan</label><input id="planName" value="${ui5Esc(p.name)}" oninput="ui5RefreshPlanStats()"></div>
        <div class="field span-7"><label>Notas</label><input id="planNotes" value="${ui5Esc(p.notes)}" oninput="ui5RefreshPlanStats()"></div>
      </div>
      <div class="ui5-plan-actions">
        <button class="btn" onclick="ui5SaveEditablePlan()">Guardar cambios</button>
        <button class="btn secondary" onclick="ui5AddPlanDay()">Añadir día</button>
        <button class="btn secondary" onclick="ui5CompletePlanWeek()">Completar semana</button>
        <button class="btn secondary" onclick="ui5ApplyDefaultPlan()">Cargar plan base</button>
        <button class="btn secondary" onclick="ui5ExportPlanJson()">Copiar/mostrar JSON</button>
      </div>
    </section>

    <section id="ui5PlanBoard" class="ui5-edit-plan-board">
      ${(p.days||[]).map(ui5PlanDayHtml).join('')}
    </section>

    <section class="card ui5-plan-json">
      <h3>JSON del plan</h3>
      <p class="muted">Para importar otro plan: pega JSON y pulsa importar.</p>
      <textarea id="planRaw" placeholder='{"name":"Semana...","days":[...]}'></textarea>
      <button class="btn secondary" onclick="savePlan()">Importar JSON pegado</button>
    </section>`;
}

/* DPP_UI5_PLAN_EDITOR_END */


/* DPP_V012_SCORE_HOME_START */
function dpp12Text(v){
  return String(v ?? '')
    .replace(/prote\?na/g, 'prote\u00edna')
    .replace(/Prote\?na/g, 'Prote\u00edna')
    .replace(/sem\?foro/g, 'sem\u00e1foro')
    .replace(/d\?a/g, 'd\u00eda')
    .replace(/d\?as/g, 'd\u00edas')
    .replace(/at\?n/g, 'at\u00fan')
    .replace(/jam\?n/g, 'jam\u00f3n')
    .replace(/m\?ximo/g, 'm\u00e1ximo')
    .replace(/\?ltimos/g, '\u00faltimos')
    .replace(/Todav\?a/g, 'Todav\u00eda')
    .replace(/todav\?a/g, 'todav\u00eda')
    .replace(/ma\?ana/g, 'ma\u00f1ana')
    .replace(/v0\.0\.12\.1/g, 'v0.0.19')
    .replace(/v0\.0\.12-dev/g, 'v0.0.19')
    .replace(/Dashboard inteligente \?/g, 'Dashboard \u00b7')
    .replace(/Dashboard \?/g, 'Dashboard \u00b7')
    .replace(/Dieta controlada \?/g, 'Dieta controlada \u00b7')
    .replace(/5 g normal \? 10/g, '5 g normal \u00b7 10')
    .replace(/min \? /g, 'min \u00b7 ')
    .replace(/\s\?\s/g, ' \u00b7 ');
}

function dpp12Version(){
  document.title = 'Diet Pro Planner \u00b7 v0.0.19';
  const eyebrow = document.querySelector('.eyebrow');
  if(eyebrow) eyebrow.textContent = 'Dieta controlada \u00b7 v0.0.19';
  const badge = document.querySelector('#ui5Badge');
  if(badge) badge.textContent = 'v0.0.19';
}

async function dpp12Insights(d){
  const r = await fetch(`/api/insights/today?date=${encodeURIComponent(d || day())}`);
  if(!r.ok){
    let msg='Error cargando dashboard';
    try{ msg=(await r.json()).error || msg; }catch(e){}
    throw new Error(msg);
  }
  return r.json();
}

function dpp12Dot(s){
  return s === 'green' ? '&#128994;' : s === 'yellow' ? '&#128993;' : '&#128308;';
}

function dpp12Status(s){
  return s === 'green' ? 'bien' : s === 'yellow' ? 'cuidado' : 'corregir';
}

function dpp12MiniCard(label, value, sub, status){
  return `<article class="dpp12-mini ${status || 'info'}">
    <span>${dpp12Text(label)}</span>
    <b>${dpp12Text(value)}</b>
    <small>${dpp12Text(sub || '')}</small>
  </article>`;
}

function dpp12Card(c){
  const pct = Math.max(0, Math.min(100, Number(c.pct || 0)));
  return `<article class="dpp12-card ${c.status || 'info'}">
    <div><span>${dpp12Text(c.label)}</span><b>${dpp12Text(c.value)}</b></div>
    <i><em style="width:${pct}%"></em></i>
    <small>${dpp12Text(c.sub || '')}</small>
  </article>`;
}

function dpp12Advice(a){
  const ico = a.severity === 'good' ? '&#9989;' : a.severity === 'bad' ? '&#128680;' : a.severity === 'warn' ? '&#9888;&#65039;' : '&#128161;';
  return `<article class="dpp12-advice ${a.severity || 'info'}">
    <span>${ico}</span>
    <div><b>${dpp12Text(a.title)}</b><small>${dpp12Text(a.text)}</small></div>
  </article>`;
}

function dpp12Weight(ins){
  const w = ins.weight || {};
  if(w.current_kg == null){
    return `<section class="dpp12-weight"><div><span>Peso hacia 80 kg</span><b>--</b><small>Sin peso registrado</small></div></section>`;
  }
  const start = Number(w.start_kg || w.current_kg || 0);
  const goal = Number(w.goal_kg || 80);
  const current = Number(w.current_kg || 0);
  const total = Math.max(0.1, start - goal);
  const lost = Math.max(0, start - current);
  const pct = Math.max(0, Math.min(100, lost / total * 100));
  const trend = dpp12Text((w.trend || {}).label || 'Sin tendencia');
  const eta = w.eta ? ` \u00b7 objetivo ${w.eta}` : '';

  return `<section class="dpp12-weight">
    <div class="dpp12-weight-main">
      <span>Peso hacia 80 kg</span>
      <b>${fmt(current)} kg</b>
      <small>${trend}${eta}</small>
    </div>
    <div class="dpp12-weight-progress">
      <i><em style="width:${pct}%"></em></i>
      <div>
        <span><b>${fmt(w.kg_lost ?? lost)}</b><small>kg perdidos</small></span>
        <span><b>${fmt(w.kg_remaining ?? Math.max(0,current-goal))}</b><small>kg restantes</small></span>
        <span><b>${fmt(goal)}</b><small>objetivo</small></span>
      </div>
    </div>
  </section>`;
}

function dpp12Sport(ins){
  const w = ins.week || {};
  const t = ins.workouts || {};
  return `<div class="dpp12-sport">
    <article><span>Hoy</span><b>${fmt(t.kcal || 0)} kcal</b><small>${fmt(t.minutes || 0)} min \u00b7 ${t.count || 0} sesiones</small></article>
    <article><span>7 d\u00edas</span><b>${fmt(w.kcal || 0)} kcal</b><small>${fmt(w.minutes || 0)} min \u00b7 ${w.count || 0} sesiones</small></article>
  </div>`;
}

function dpp12RenderHome(ins){
  const meals = byDate(state.meals, ins.date);
  const workouts = byDate(state.workouts, ins.date);
  const sem = ins.semaphore || 'yellow';
  const cards = (ins.cards || []).filter(c => c.kind !== 'weight').map(dpp12Card).join('');
  const advice = (ins.advice || []).map(dpp12Advice).join('');
  const scoreSub = `${dpp12Status(sem)} \u00b7 ${fmt(ins.estimated_deficit || 0)} kcal margen`;

  return `
    ${dateBar()}

    <section class="dpp12-hero ${sem}">
      <div>
        <span class="dpp12-kicker">Dashboard v0.0.19</span>
        <h2>${dpp12Dot(sem)} ${dpp12Text(ins.semaphore_label || 'Estado')}</h2>
        <p>${dpp12Text(ins.main_action || '')}</p>
      </div>
      <div class="dpp12-score">
        <b>${ins.score}</b>
        <small>${scoreSub}</small>
      </div>
    </section>

    ${dpp12Weight(ins)}

    <section class="dpp12-cards">${cards}</section>

    <section class="dpp12-grid">
      <article class="card dpp12-panel">
        <header><h3>Qu\u00e9 hacer hoy</h3><span>${(ins.advice || []).length} reglas</span></header>
        <div class="dpp12-advice-list">${advice}</div>
      </article>

      <article class="card dpp12-panel">
        <header><h3>Deporte</h3><button class="btn small" onclick="go('sport')">+ Entreno</button></header>
        ${dpp12Sport(ins)}
      </article>
    </section>

    <details class="card dpp12-details">
      <summary><span>Peso oficial y registros</span><b>${meals.length} comida${meals.length===1?'':'s'} \u00b7 ${workouts.length} entreno${workouts.length===1?'':'s'}</b></summary>
      <div class="dpp12-records">
        <section>
          <h3>Peso oficial</h3>
          ${weightChart()}
        </section>
        <section>
          <h3>Comidas</h3>
          <div class="compact-list">${meals.length ? meals.map(mealCardCompact).join('') : '<div class="empty">Sin comidas.</div>'}</div>
        </section>
        <section>
          <h3>Actividad</h3>
          <div class="compact-list">${workouts.length ? workouts.map(workoutCardCompact).join('') : '<div class="empty">Sin entrenos para este d\u00eda.</div>'}</div>
        </section>
      </div>
    </details>
    <div class="footer-space"></div>
  `;
}

renderHome = function(){
  document.body.classList.add('dpp12-home');
  dpp12Version();
  const d = day();
  $('#view').innerHTML = `${dateBar()}<div class="card"><h3>Cargando dashboard...</h3><p class="muted">Calculando score, peso, comida y deporte.</p></div>`;
  dpp12Insights(d).then(ins => {
    if(day() !== d) return;
    $('#view').innerHTML = dpp12RenderHome(ins);
    dpp12Version();
  }).catch(err => {
    $('#view').innerHTML = `${dateBar()}<div class="card note-box"><h3>No pude cargar el dashboard</h3><p>${dpp12Text(err.message)}</p></div>`;
    dpp12Version();
  });
};

window.renderHome = renderHome;
setInterval(dpp12Version, 1000);
/* DPP_V012_SCORE_HOME_END */


/* DPP_FI_SINGLE_HOME_START */
/* v0.0.19 · Single premium home powered by Food Intelligence. */

(function(){
  if(window.__DPP_FI_SINGLE_HOME__) return;
  window.__DPP_FI_SINGLE_HOME__ = true;

  function fiEsc(v){
    return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function fiFmt(v, digits=1){
    try{
      return Number(v || 0).toLocaleString('es-ES', {maximumFractionDigits:digits});
    }catch(e){
      return String(v ?? '');
    }
  }

  function fiClean(v){
    return String(v ?? '')
      .replace(/Buen dia/g,'Buen día')
      .replace(/Proteina/g,'Proteína')
      .replace(/proteina/g,'proteína')
      .replace(/Energia/g,'Energía')
      .replace(/energia/g,'energía')
      .replace(/manana/g,'mañana')
      .replace(/Opcion/g,'Opción')
      .replace(/\bdia\b/g,'día')
      .replace(/\bDia\b/g,'Día')
      .replace(/medía/g,'media')
      .replace(/atun/g,'atún')
      .replace(/jamon/g,'jamón')
      .replace(/platano/g,'plátano')
      
      .replace(/m\?s/g,'más')
      .replace(/Mantún/g,'Mantén');
  }

  async function fiApi(path, opts){
    const r = await fetch(path, opts || {});
    if(!r.ok) throw new Error('Error cargando inteligencia');
    return await r.json();
  }

  async function fiDay(d){
    return fiApi(`/api/food-intel/day?date=${encodeURIComponent(d)}`);
  }

  async function fiMealPlan(d){
    return fiApi('/api/food-intel/meal-plan', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        date:d,
        meal:'next',
        training_today:false,
        available_foods:[]
      })
    });
  }

  function fiLatestWeight(){
    try{return latestWeight();}catch(e){return null;}
  }

  function fiWeightBlock(){
    const lw = fiLatestWeight();
    const goal = 80;
    const current = Number(lw?.kg || 0);
    const start = 86.7;
    const lost = Math.max(0, start - current);
    const remaining = Math.max(0, current - goal);
    const pct = Math.max(0, Math.min(100, lost / Math.max(.1, start - goal) * 100));

    if(!lw){
      return `
        <section class="fi13-weight">
          <div><span>Peso hacia 80 kg</span><b>Sin dato</b><small>Registra peso oficial</small></div>
        </section>`;
    }

    return `
      <section class="fi13-weight">
        <div class="fi13-weight-main">
          <span>Peso hacia 80 kg</span>
          <b>${fiFmt(current,2)} kg</b>
          <small>${fiEsc(lw.date || '')} · ${lw.official ? 'oficial' : 'referencia'}</small>
        </div>
        <div class="fi13-weight-progress">
          <i><em style="width:${pct}%"></em></i>
          <div>
            <span><b>${fiFmt(lost,1)}</b><small>kg perdidos</small></span>
            <span><b>${fiFmt(remaining,1)}</b><small>kg restantes</small></span>
            <span><b>${goal}</b><small>objetivo</small></span>
          </div>
        </div>
      </section>`;
  }

  function fiMetric(label, value, sub, tone){
    return `
      <article class="fi13-metric ${tone || 'ok'}">
        <span>${fiEsc(label)}</span>
        <b>${fiEsc(value)}</b>
        <small>${fiEsc(fiClean(sub || ''))}</small>
      </article>`;
  }

  function fiRecommendations(data){
    const recs = ((data.analysis || {}).recommendations || []).slice(0,3);
    if(!recs.length) return '<li>Sin alertas relevantes.</li>';
    return recs.map(x => `<li>${fiEsc(fiClean(x))}</li>`).join('');
  }

  function fiMealSummary(){
    const meals = byDate(state.meals);
    const workouts = byDate(state.workouts);
    const mt = mealTotals(meals);
    const sport = workoutTotals(workouts);

    return `
      <section class="fi13-lower-grid">
        <article class="card fi13-panel">
          <header>
            <div>
              <h3>Comidas registradas</h3>
              <p>${fiFmt(mt.kcal,1)} kcal · ${fiFmt(mt.protein,1)} g proteína</p>
            </div>
            <button class="btn small" onclick="go('register')">+ Comida</button>
          </header>
          <div class="compact-list">${meals.length ? meals.map(mealCardCompact).join('') : '<div class="empty">Sin comidas.</div>'}</div>
        </article>

        <article class="card fi13-panel">
          <header>
            <div>
              <h3>Actividad</h3>
              <p>${fiFmt(sport,1)} kcal</p>
            </div>
            <button class="btn small" onclick="go('sport')">+ Entreno</button>
          </header>
          <div class="compact-list">${workouts.length ? workouts.map(workoutCardCompact).join('') : '<div class="empty">Sin entrenos para este día.</div>'}</div>
        </article>
      </section>`;
  }

  function fiSuggestionsHtml(payload){
    const opts = (((payload || {}).plan || {}).options || []).slice(0,3);
    if(!opts.length) return '<div class="empty">No hay sugerencias suficientes.</div>';

    return opts.map(opt => {
      const t = opt.totals || {};
      const items = (opt.items || []).map(it => `<li>${fiEsc(fiClean(it.food_name))} · ${fiFmt(it.grams,0)} g</li>`).join('');
      return `
        <article>
          <div>
            <b>${fiEsc(fiClean(opt.title || 'Opción'))}</b>
            <small>${fiFmt(t.kcal,0)} kcal · ${fiFmt(t.protein,1)} g proteína · fit ${fiEsc(opt.fit_score ?? '--')}</small>
          </div>
          <ul>${items}</ul>
          <p>${fiEsc(fiClean(opt.why || ''))}</p>
        </article>`;
    }).join('');
  }


  async function fiBodySnapshotHtml(){
    try{
      const r = await fetch('/api/body-snapshot/latest', {cache:'no-store'});
      if(!r.ok) return '';
      const data = await r.json();
      if(!data || !data.available) return '';

      const m = data.metrics || {};
      const d = data.derived || {};
      const v = (k) => (m[k] || {}).value;
      const fmt2 = (x, dec=1) => {
        if(x === null || x === undefined || x === '') return '--';
        try{return Number(x).toLocaleString('es-ES', {maximumFractionDigits:dec});}
        catch(e){return String(x);}
      };

      const weight = v('weight');
      const fat = v('body_fat_pct');
      const water = v('water_pct');
      const muscle = v('muscle_mass_kg');
      const visceral = v('visceral_fat');
      const bio = v('biocharge_wakeup');

      return `
        <section id="dppBodySnapshotCard" class="bs14-card bs14-compact">
          <div class="bs14-topline">
            <div>
              <span>Foto corporal · v0.0.19</span>
              <h3>Composición corporal</h3>
              <p>${data.date || ''} ${data.time ? '· ' + data.time : ''} · lectura opcional de báscula</p>
            </div>
            <div class="bs14-status-pill">
              <b>${fmt2(bio,0)}</b>
              <small>BioCharge</small>
            </div>
          </div>

          <div class="bs14-compact-body">
            <div class="bs14-mini-person">
              <div class="bs14-person">
                <i class="head"></i>
                <i class="torso"></i>
                <i class="legs"></i>
              </div>
              <div>
                <b>${fmt2(fat,1)}% grasa</b>
                <small>${fmt2(water,1)}% agua · ${fmt2(muscle,1)} kg músculo · ${d.fat_mass_kg ? fmt2(d.fat_mass_kg,1) + ' kg grasa' : 'bioimpedancia'}</small>
              </div>
            </div>

            <div class="bs14-compact-grid">
              <article class="watch"><span>Grasa</span><b>${fmt2(fat,1)}%</b></article>
              <article><span>Agua</span><b>${fmt2(water,1)}%</b></article>
              <article><span>Músculo</span><b>${fmt2(muscle,1)} kg</b></article>
              <article class="watch"><span>Visceral</span><b>${fmt2(visceral,0)}</b></article>
            </div>
          </div>

          <p class="bs14-note">Dato estimado por bioimpedancia. Úsalo como tendencia semanal, no para juzgar un peso aislado. Detalle completo en Peso 2.0 próximamente.</p>
        </section>
      `;
    }catch(e){
      return '';
    }
  }


  function fiHomeHtml(data, bodySnapshotHtml=''){
    const a = data.analysis || {};
    const rules = a.rules || {};
    const summary = data.summary || {};
    const conf = data.confidence || {};
    const meals = byDate(state.meals);
    const workouts = byDate(state.workouts);

    const protein = rules.protein || {};
    const energy = rules.energy || {};
    const oil = rules.oil || {};
    const activity = rules.training_alignment || {};
    const salt = rules.salt || {};

    return `
      ${dateBar()}

      <section class="fi13-hero ${fiEsc(a.semaphore || 'green')}">
        <div>
          <span class="fi13-kicker">Inteligencia del día · v0.0.19</span>
          <h2>${fiEsc(fiClean(a.label || 'Análisis'))}</h2>
          <p>${fiEsc(fiClean(a.main_action || 'Analizando día.'))}</p>
          <div class="fi13-hero-tags">
            <span>Confianza ${fiEsc(fiClean(conf.label || 'media'))}</span>
            <span>${fiEsc((conf.reasons || []).slice(0,1).join(' · ') || 'datos locales')}</span>
          </div>
        </div>
        <div class="fi13-score">
          <b>${a.score == null ? '--' : fiEsc(a.score)}</b>
          <small>score</small>
        </div>
      </section>

      ${fiWeightBlock()}

      ${bodySnapshotHtml || ''}

      <section class="fi13-metrics">
        ${fiMetric('Proteína', `${fiFmt(summary.protein,1)} g`, protein.message || 'objetivo 130-150 g', protein.status === 'ok' ? 'ok' : 'watch')}
        ${fiMetric('Energía', `${fiFmt(a.kcal_margin,0)} kcal`, 'margen vs objetivo', energy.status === 'ok' ? 'ok' : 'watch')}
        ${fiMetric('Aceite', `${fiFmt(summary.oil_g,1)} g`, oil.message || 'aceite medido', oil.status === 'ok' ? 'ok' : 'watch')}
        ${fiMetric('Entreno', `${fiFmt((data.workouts || {}).kcal,0)} kcal`, activity.message || 'sin entreno', activity.status === 'ok' ? 'ok' : 'watch')}
      </section>

      <section class="fi13-main-grid">
        <article class="card fi13-panel fi13-next">
          <header>
            <div>
              <h3>Qué hacer ahora</h3>
              <p>${meals.length} comidas · ${workouts.length} entrenos · sal ${salt.status === 'watch' ? 'a vigilar' : 'ok'}</p>
            </div>
            <button id="fi13SuggestBtn" class="btn small">Sugerir comida</button>
          </header>
          <ul>${fiRecommendations(data)}</ul>
          <div id="fi13Suggestions" class="fi13-suggestions"></div>
        </article>

        <article class="card fi13-panel">
          <header><div><h3>Peso oficial</h3><p>Lecturas recientes</p></div></header>
          ${weightChart()}
        </article>
      </section>

      ${fiMealSummary()}

      <div class="footer-space"></div>`;
  }

  async function fiRenderHome(){
    document.body.classList.add('fi13-home');
    const d = day();

    $('#view').innerHTML = `
      ${dateBar()}
      <section class="card fi13-loading">
        <h3>Cargando inteligencia del día.</h3>
        <p class="muted">Calculando comida, peso, deporte, confianza y recomendaciones.</p>
      </section>`;

    try{
      const data = await fiDay(d);
      const bodySnapshotHtml = await fiBodySnapshotHtml();
      if(day() !== d) return;
      $('#view').innerHTML = fiHomeHtml(data, bodySnapshotHtml);

      const btn = document.querySelector('#fi13SuggestBtn');
      if(btn){
        btn.onclick = async function(){
          const box = document.querySelector('#fi13Suggestions');
          btn.disabled = true;
          btn.textContent = 'Calculando...';
          try{
            const payload = await fiMealPlan(d);
            if(box) box.innerHTML = fiSuggestionsHtml(payload);
          }catch(e){
            if(box) box.innerHTML = '<div class="empty">No pude generar sugerencias.</div>';
          }finally{
            btn.disabled = false;
            btn.textContent = 'Sugerir comida';
          }
        };
      }
    }catch(e){
      $('#view').innerHTML = `
        ${dateBar()}
        <section class="card note-box">
          <h3>No pude cargar Food Intelligence</h3>
          <p>${fiEsc(e.message || 'Error')}</p>
        </section>`;
    }
  }

  renderHome = fiRenderHome;
  window.renderHome = fiRenderHome;

  const prevRender = window.render || render;
  window.render = function(){
    document.body.classList.toggle('fi13-home', page === 'home');
    return prevRender();
  };
})();
/* DPP_FI_SINGLE_HOME_END */







/* DPP_V0141_WEIGHT_INPUT_HOTFIX_START */
(function(){
  function clearDangerousWeightDefault(){
    const w = document.querySelector('#wKg');
    if(!w) return;
    const v = String(w.value || '').trim();
    if(v === '86.70' || v === '86.7'){
      w.value = '';
    }
    w.placeholder = 'kg de hoy';
  }
  document.addEventListener('DOMContentLoaded', clearDangerousWeightDefault);
  const obs = new MutationObserver(() => setTimeout(clearDangerousWeightDefault, 80));
  obs.observe(document.body, {childList:true, subtree:true});
  setInterval(clearDangerousWeightDefault, 1500);
})();
/* DPP_V0141_WEIGHT_INPUT_HOTFIX_END */

/* DPP_V0141_MEAL_TOTALS_SOURCE_FIX_START */
(function(){
  "use strict";

  const FLAG = "__dpp_food_intel_totals_v016-release";
  const CACHE = {};
  let hydrating = false;
  let rerendering = false;

  function n(x, fallback){
    const v = Number(x);
    return Number.isFinite(v) ? v : (fallback || 0);
  }

  function round1(x){
    return Math.round(n(x) * 10) / 10;
  }

  function normText(x){
    return String(x || "")
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function selectedDateSafe(){
    try {
      if (typeof selectedDate !== "undefined" && selectedDate) return selectedDate;
    } catch(e) {}

    try {
      const saved = localStorage.getItem("selectedDate");
      if (saved) return saved;
    } catch(e) {}

    const input = document.querySelector('input[type="date"]');
    if (input && input.value) return input.value;

    const body = (document.body && (document.body.innerText || document.body.textContent) || "");
    const m = body.match(/\b(\d{2})\/(\d{2})\/(\d{4})\b/);
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;

    return new Date().toISOString().slice(0, 10);
  }

  function mealMarker(meal){
    const notes = String(meal && meal.notes || "");
    const m = notes.match(/\bREAL_[A-Z0-9_]+\b/);
    return m ? m[0] : "";
  }

  function mealKey(meal){
    return `${String(meal && meal.time || "").trim()}|${normText(meal && meal.name || "")}`;
  }

  function itemName(it){
    return it && (it.name || it.food_name || it.food || it.label || "");
  }

  function itemKey(it){
    return `${normText(itemName(it))}|${Math.round(n(it && it.grams) * 10) / 10}`;
  }

  function mealArraysInState(){
    const out = [];

    try {
      if (typeof state !== "undefined" && state) {
        if (Array.isArray(state.meals)) out.push(state.meals);
        if (state.day && Array.isArray(state.day.meals)) out.push(state.day.meals);
        if (state.summary && Array.isArray(state.summary.meals)) out.push(state.summary.meals);
      }
    } catch(e) {}

    return [...new Set(out)];
  }

  function buildIntelMaps(intelMeals){
    const byId = new Map();
    const byMarker = new Map();
    const byKey = new Map();

    for (const m of intelMeals) {
      if (m && m.id !== undefined && m.id !== null) byId.set(String(m.id), m);

      const marker = mealMarker(m);
      if (marker) byMarker.set(marker, m);

      const key = mealKey(m);
      if (key !== "|") byKey.set(key, m);
    }

    return {byId, byMarker, byKey};
  }

  function findIntelMeal(localMeal, maps){
    if (!localMeal) return null;

    if (localMeal.id !== undefined && localMeal.id !== null) {
      const byId = maps.byId.get(String(localMeal.id));
      if (byId) return byId;
    }

    const marker = mealMarker(localMeal);
    if (marker && maps.byMarker.has(marker)) return maps.byMarker.get(marker);

    const key = mealKey(localMeal);
    if (maps.byKey.has(key)) return maps.byKey.get(key);

    return null;
  }

  function applyTotalsAliases(meal, totals){
    if (!meal || !totals) return false;

    const kcal = n(totals.kcal);
    const protein = n(totals.protein);
    const carbs = n(totals.carbs);
    const fat = n(totals.fat);
    const salt = n(totals.salt);
    const sugar = n(totals.sugar);

    const cleanTotals = {
      kcal,
      protein: round1(protein),
      carbs: round1(carbs),
      fat: round1(fat),
      salt: round1(salt),
      sugar: round1(sugar),
    };

    meal.totals = Object.assign({}, meal.totals || {}, cleanTotals);
    meal.macros = Object.assign({}, meal.macros || {}, cleanTotals);
    meal.nutrients = Object.assign({}, meal.nutrients || {}, cleanTotals);

    // Aliases probables que el render viejo puede estar usando.
    meal.kcal = kcal;
    meal.calories = kcal;
    meal.energy_kcal = kcal;
    meal.total_kcal = kcal;
    meal.protein = round1(protein);
    meal.protein_g = round1(protein);
    meal.total_protein = round1(protein);
    meal.carbs = round1(carbs);
    meal.fat = round1(fat);
    meal.salt = round1(salt);
    meal.sugar = round1(sugar);

    meal[FLAG] = true;
    return true;
  }

  function applyItemMacros(localMeal, intelMeal){
    const localItems = Array.isArray(localMeal && localMeal.items) ? localMeal.items : [];
    const intelItems = Array.isArray(intelMeal && intelMeal.items) ? intelMeal.items : [];

    if (!localItems.length || !intelItems.length) return 0;

    const intelByKey = new Map();
    for (const it of intelItems) {
      intelByKey.set(itemKey(it), it);
    }

    let changed = 0;

    for (let i = 0; i < localItems.length; i++) {
      const lit = localItems[i];
      const iit = intelByKey.get(itemKey(lit)) || intelItems[i];

      if (!iit || !iit.macros) continue;

      const macros = iit.macros;
      const kcal = n(macros.kcal);
      const protein = round1(macros.protein);

      lit.macros = Object.assign({}, lit.macros || {}, macros);
      lit.nutrients = Object.assign({}, lit.nutrients || {}, macros);

      lit.kcal = kcal;
      lit.calories = kcal;
      lit.energy_kcal = kcal;
      lit.protein = protein;
      lit.protein_g = protein;
      lit.carbs = round1(macros.carbs);
      lit.fat = round1(macros.fat);
      lit.salt = round1(macros.salt);
      lit.sugar = round1(macros.sugar);

      if (!lit.name && iit.name) lit.name = iit.name;
      if (!lit.food_name && iit.name) lit.food_name = iit.name;
      if (!lit.grams && iit.grams) lit.grams = iit.grams;

      lit[FLAG] = true;
      changed++;
    }

    return changed;
  }

  function mergeFoodIntelIntoState(intel){
    const intelMeals = Array.isArray(intel && intel.meals) ? intel.meals : [];
    if (!intelMeals.length) return 0;

    const maps = buildIntelMaps(intelMeals);
    const arrays = mealArraysInState();

    let changed = 0;

    for (const arr of arrays) {
      for (const localMeal of arr) {
        const intelMeal = findIntelMeal(localMeal, maps);
        if (!intelMeal) continue;

        if (applyTotalsAliases(localMeal, intelMeal.totals || {})) changed++;
        applyItemMacros(localMeal, intelMeal);
      }
    }

    try {
      if (typeof state !== "undefined" && state) {
        state.foodIntel = intel;
        state.dayIntel = intel;
      }
    } catch(e) {}

    return changed;
  }

  async function fetchFoodIntel(date){
    if (CACHE[date]) return CACHE[date];

    const url = `/api/food-intel/day?date=${encodeURIComponent(date)}`;
    let data;

    if (typeof api === "function") {
      data = await api(url);
    } else {
      const r = await fetch(url, {cache: "no-store"});
      if (!r.ok) throw new Error(`food-intel ${r.status}`);
      data = await r.json();
    }

    CACHE[date] = data;
    return data;
  }

  async function hydrateFoodIntelAndMaybeRender(forceRender){
    if (hydrating) return 0;
    hydrating = true;

    try {
      const date = selectedDateSafe();
      const intel = await fetchFoodIntel(date);
      const changed = mergeFoodIntelIntoState(intel);

      if (changed && forceRender && typeof render === "function" && !rerendering) {
        rerendering = true;
        try {
          render();
        } finally {
          rerendering = false;
        }
      }

      if (changed) {
        console.info(`[DPP] Food Intel totals merged into meal state: ${changed} meals date=${date}`);
      }

      return changed;
    } catch(err) {
      console.warn("[DPP] Food Intel totals source fix skipped:", err);
      return 0;
    } finally {
      hydrating = false;
    }
  }

  try {
    if (typeof load === "function" && !load.__dppFoodIntelWrapped) {
      const originalLoad = load;
      load = async function(){
        const out = await originalLoad.apply(this, arguments);
        await hydrateFoodIntelAndMaybeRender(false);
        return out;
      };
      load.__dppFoodIntelWrapped = true;
    }
  } catch(e) {
    console.warn("[DPP] load wrapper unavailable:", e);
  }

  try {
    if (typeof render === "function" && !render.__dppFoodIntelWrapped) {
      const originalRender = render;
      render = function(){
        if (!rerendering) {
          hydrateFoodIntelAndMaybeRender(true);
        }
        return originalRender.apply(this, arguments);
      };
      render.__dppFoodIntelWrapped = true;
    }
  } catch(e) {
    console.warn("[DPP] render wrapper unavailable:", e);
  }

  document.addEventListener("DOMContentLoaded", function(){
    hydrateFoodIntelAndMaybeRender(true);
  });

  setTimeout(function(){ hydrateFoodIntelAndMaybeRender(true); }, 100);
  setTimeout(function(){ hydrateFoodIntelAndMaybeRender(true); }, 800);
})();
/* DPP_V0141_MEAL_TOTALS_SOURCE_FIX_END */

/* DPP_V0141_UI_CLEANUP_START */
(function(){
  "use strict";

  function textOf(el){
    return (el && (el.innerText || el.textContent) || "").replace(/\s+/g, " ").trim();
  }

  function walkTextNodes(root, fn){
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node;
    while ((node = walker.nextNode())) nodes.push(node);
    for (const n of nodes) fn(n);
  }

  function fixFalseChocolateAdvice(){
    const body = textOf(document.body);

    const hasProteinChocolate =
      /batido proteico chocolate/i.test(body) ||
      /alpro protein cacao/i.test(body);

    const hasRealChocolate =
      /chocolate onzas/i.test(body) ||
      /onza[s]? chocolate/i.test(body) ||
      /chocolate post/i.test(body) ||
      /chocolate pre/i.test(body);

    if (!hasProteinChocolate || hasRealChocolate) return;

    walkTextNodes(document.body, function(node){
      let v = node.nodeValue || "";
      const old = v;

      v = v.replace(
        /No añadas más extras hoy:\s*chocolate\.?/gi,
        "Evita aceite extra y picoteo después del pádel."
      );

      v = v.replace(
        /Extras detectados:\s*chocolate/gi,
        "Extras controlados"
      );

      if (v !== old) node.nodeValue = v;
    });
  }

  function bestBlockContaining(required){
    const selectors = "section, article, .card, .panel, .tile, .summary-card, .metric-card, div";
    const items = Array.from(document.querySelectorAll(selectors))
      .filter(el => {
        const t = textOf(el);
        return required.every(x => t.includes(x));
      });

    if (!items.length) return null;
    items.sort((a,b) => textOf(a).length - textOf(b).length);
    return items[0];
  }

  function moveBodyCompositionDown(){
    const bio = bestBlockContaining(["Foto corporal", "BioCharge"]);
    if (!bio || bio.dataset.dppMovedBio === "1") return;

    const meals = bestBlockContaining(["Comidas registradas"]);
    const activity = bestBlockContaining(["Actividad"]);

    // Lo colocamos después de comidas si existe, antes de actividad si puede.
    try {
      if (activity && activity.parentNode && activity !== bio && !bio.contains(activity)) {
        activity.parentNode.insertBefore(bio, activity);
        bio.dataset.dppMovedBio = "1";
      } else if (meals && meals.parentNode && meals !== bio && !bio.contains(meals)) {
        meals.parentNode.insertBefore(bio, meals.nextSibling);
        bio.dataset.dppMovedBio = "1";
      }
    } catch(e) {
      // Si el layout no permite moverlo, no rompemos nada.
      console.warn("[DPP] BioCharge reorder skipped:", e);
    }
  }

  function applyCleanup(){
    fixFalseChocolateAdvice();
    moveBodyCompositionDown();
  }

  function scheduleCleanup(){
    setTimeout(applyCleanup, 50);
    setTimeout(applyCleanup, 300);
    setTimeout(applyCleanup, 900);
  }

  try {
    if (typeof render === "function" && !render.__dppUiCleanupWrapped) {
      const oldRender = render;
      render = function(){
        const out = oldRender.apply(this, arguments);
        scheduleCleanup();
        return out;
      };
      render.__dppUiCleanupWrapped = true;
    }
  } catch(e) {
    console.warn("[DPP] UI cleanup render hook skipped:", e);
  }

  document.addEventListener("DOMContentLoaded", scheduleCleanup);
  window.addEventListener("focus", scheduleCleanup);
  setInterval(applyCleanup, 2000);
  scheduleCleanup();
})();
/* DPP_V0141_UI_CLEANUP_END */
