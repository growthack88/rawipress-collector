// Analytics charts — pulls /api/dashboard and renders with Chart.js.
const EM = "#10b981", EM2 = "#34d399", BLUE = "#5fb3d4", AMBER = "#f0b252", GRID = "#1c2a30", INK = "#7e9690";
Chart.defaults.color = INK;
Chart.defaults.font.family = "SF Mono, ui-monospace, monospace";
Chart.defaults.borderColor = GRID;

const palette = ["#10b981","#34d399","#5fb3d4","#f0b252","#f1607a","#8b9df0","#0c6f53","#1b5e7e"];

function bar(id, labels, data, color){
  new Chart(document.getElementById(id), {
    type:"bar",
    data:{labels, datasets:[{data, backgroundColor:color||EM, borderRadius:5, maxBarThickness:34}]},
    options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:GRID}},x:{grid:{display:false}}}}
  });
}
function doughnut(id, labels, data){
  new Chart(document.getElementById(id), {
    type:"doughnut",
    data:{labels, datasets:[{data, backgroundColor:palette, borderColor:"#0d1418", borderWidth:2}]},
    options:{cutout:"62%",plugins:{legend:{position:"right",labels:{boxWidth:12,font:{size:11}}}}}
  });
}

fetch("/api/dashboard").then(r=>r.json()).then(d=>{
  const day = d.by_day||{};
  bar("cDay", Object.keys(day), Object.values(day), EM2);

  const src = d.by_source||{};
  bar("cSource", Object.keys(src).slice(0,8), Object.values(src).slice(0,8), BLUE);

  const cat = d.by_category||{};
  doughnut("cCat", Object.keys(cat).slice(0,8), Object.values(cat).slice(0,8));

  const lang = d.by_language||{};
  doughnut("cLang", Object.keys(lang), Object.values(lang));

  const kw = document.getElementById("kw");
  (d.trending_keywords||[]).forEach(([w,c])=>{
    const s=document.createElement("span"); s.className="kw"; s.textContent=`${w} ·${c}`; kw.appendChild(s);
  });
  if(!(d.trending_keywords||[]).length) kw.innerHTML='<span class="muted">No keywords yet.</span>';

  const ent = document.getElementById("ent");
  const te = d.top_entities||{};
  ["organizations","people","locations"].forEach(g=>{
    if((te[g]||[]).length){
      const row=document.createElement("div"); row.className="ent-row";
      row.innerHTML=`<div class="lbl">${g.toUpperCase()}</div>`+
        '<div class="chips">'+te[g].map(([n,c])=>`<span class="chip">${n} ·${c}</span>`).join("")+'</div>';
      ent.appendChild(row);
    }
  });
  if(!ent.children.length) ent.innerHTML='<span class="muted">No entities yet.</span>';
});
