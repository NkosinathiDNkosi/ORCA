const menuBtn=document.querySelector('.menu-toggle');
const nav=document.querySelector('.nav-panel');
if(menuBtn&&nav){
menuBtn.addEventListener('click',()=>nav.classList.toggle('open'));
nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>nav.classList.remove('open')))
}
const topBtn=document.getElementById('scrollTop');
window.addEventListener('scroll',()=>{
if(window.scrollY>650){
topBtn?.classList.add('show')
}
else{
topBtn?.classList.remove('show')
}
}
);
topBtn?.addEventListener('click',()=>window.scrollTo({
top:0,behavior:'smooth'
}
));
const dateInput=document.querySelector('input[name="appointment_date"]');
if(dateInput){
const d=new Date();
d.setDate(d.getDate()+1);
dateInput.min=d.toISOString().split('T')[0];
}
// Premium stats counter: slower, smoother, and only starts when the stats are visible.
const statNumbers=document.querySelectorAll('.trust-row strong');
const prefersReducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function animateStat(el){
  if(el.dataset.counted==='true') return;
  el.dataset.counted='true';
  const original=el.textContent.trim();
  const target=parseInt(original.replace(/[^0-9]/g,''),10);
  const suffix=original.replace(/[0-9]/g,'');
  if(!target || prefersReducedMotion){
    el.textContent=original;
    return;
  
}
  const duration=2600;
  const start=performance.now();
  el.textContent=`0${
suffix
}
`;
  function tick(now){
    const progress=Math.min((now-start)/duration,1);
    const eased=1-Math.pow(1-progress,3);
    const value=Math.round(target*eased);
    el.textContent=`${
value
}
${
suffix
}
`;
    if(progress<1){
requestAnimationFrame(tick)
}
else{
el.textContent=original
}
  
}
  requestAnimationFrame(tick);
}
if('IntersectionObserver' in window){
  const statsObserver=new IntersectionObserver((entries)=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        statNumbers.forEach((el,index)=>setTimeout(()=>animateStat(el),index*180));
        statsObserver.disconnect();
      
}
    
}
);
  
}
,{
threshold:.45
}
);
  const trustRow=document.querySelector('.trust-row');
  if(trustRow){
statsObserver.observe(trustRow)
}
}
else{
  statNumbers.forEach((el,index)=>setTimeout(()=>animateStat(el),index*180));
}
