(() => {
'use strict';
const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
let reduce = motionPreference.matches;
const $ = s => document.querySelector(s);

/* ================= WebGL red fog ================= */
const sky = $('#sky');
const gl = sky.getContext('webgl', {antialias:false, premultipliedAlpha:false});
const S = { flash:0, strike:[0,.3], tint:[.95,.12,.16], mouse:[0,0], mt:[0,0], density:.85 };
// the pointer's wake through the fog: recent path samples, faded over about a second
const W = { trail:[], last:null, pos:new Float32Array(64), dir:new Float32Array(32) };
let draw = () => {};
const initSky = () => { // builds the fog shader; runs again if the browser drops and restores the WebGL context
  const vs = `attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}`;
  const fs = `precision highp float;
  uniform vec2 uRes;uniform float uTime;uniform vec2 uMouse;uniform float uFlash;uniform vec2 uStrike;uniform vec3 uTint;uniform float uDensity;
  // the pointer's wake: the gas parts along its path and drags slightly forward, then closes back in (no darkening)
  // (a copy of frontend/src/components/shell/fogWake.ts)
  uniform vec4 uWake[16];uniform vec2 uWakeDir[16];
  vec3 wake(vec2 p){
    vec2 disp=vec2(0.);float cut=0.;
    for(int i=0;i<16;i++){
      vec4 t=uWake[i];
      if(t.z<.001) continue;
      vec2 d=p-t.xy, v=uWakeDir[i], n=vec2(-v.y,v.x);
      float along=dot(d,v), across=dot(d,n);
      float k=exp(-across*across/.000064-along*along/.000256)*t.z;
      disp+=(n*across*175.+v*.6)*k; // parts smoothly to either side, drags slightly forward
      cut+=k;
    }
    // cursor-sized band; averaged, not summed, and kept to ~0.3% of screen height so the fog never folds into rings
    return vec3(disp*.003/max(1.,cut),clamp(cut,0.,1.));
  }
  float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
  float fbm(vec2 p){float v=0.,a=.5;mat2 m=mat2(1.6,1.2,-1.2,1.6);for(int i=0;i<5;i++){v+=a*n(p);p=m*p;a*=.5;}return v;}
  void main(){
    vec2 uv=gl_FragCoord.xy/uRes;
    vec2 p=(gl_FragCoord.xy-.5*uRes)/uRes.y;
    float t=uTime*.03;
    // low, rolling fog: stretched sideways and drifting slowly
    vec3 wk=wake(p);
    vec2 cp=(p-wk.xy)*vec2(.8,1.3);
    vec2 q=vec2(fbm(cp*1.3+vec2(t,0.)),fbm(cp*1.3+vec2(5.2,1.3)-t));
    vec2 r=vec2(fbm(cp*1.3+3.2*q+vec2(1.7,9.2)+t*1.4),fbm(cp*1.3+3.2*q+vec2(8.3,2.8)-t*1.1));
    float f=fbm(cp*1.1+3.*r+uMouse*.15);
    float fog=smoothstep(.2,.95,f)*(.55+.6*(1.-uv.y*.6))*uDensity*1.5;
    float edge=smoothstep(.45,.75,f)-smoothstep(.75,1.,f);
    // the fog itself stays close to black between strikes
    vec3 col=mix(vec3(.012,.004,.005),uTint*.13,fog);
    col+=uTint*edge*.025;
    col+=uTint*.012*exp(-length(p-uMouse)*2.4)*fog*6.;
    col+=uTint*.035*smoothstep(.6,0.,uv.y);
    // lightning lights the fog from behind: brightest near the strike, carried by the fog's density and folds
    float d=length(p-uStrike);
    float reach=exp(-d*1.5)*1.5+.12;
    float lit=uFlash*reach*(.02+fog*1.1+edge*.8);
    col+=mix(uTint,vec3(1.,.8,.84),.3)*lit*.75;
    // a soft glow hanging around the bolt itself, so the light clearly comes from the strike
    col+=mix(uTint,vec3(1.,.85,.9),.5)*uFlash*exp(-d*3.2)*(.18+fog*.5);
    col*=1.-.55*pow(length(uv-.5)*1.25,2.2);
    col+=(h(gl_FragCoord.xy+fract(uTime))-.5)*.025;
    gl_FragColor=vec4(max(col,0.),1.);
  }`;
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if(!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s; };
  const pr = gl.createProgram();
  gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(pr); gl.useProgram(pr);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr,'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
  const U = {}; ['uRes','uTime','uMouse','uFlash','uStrike','uTint','uDensity','uWake','uWakeDir'].forEach(k => U[k] = gl.getUniformLocation(pr,k));
  const RES = .5; // render at half resolution; the softness reads as atmosphere
  const size = () => { sky.width = Math.round(innerWidth*RES); sky.height = Math.round(innerHeight*RES); gl.viewport(0,0,sky.width,sky.height); };
  size(); addEventListener('resize', size);
  draw = (t) => {
    gl.uniform2f(U.uRes, sky.width, sky.height); gl.uniform1f(U.uTime, t);
    gl.uniform2f(U.uMouse, S.mouse[0], S.mouse[1]); gl.uniform1f(U.uFlash, S.flash);
    gl.uniform2f(U.uStrike, S.strike[0], S.strike[1]); gl.uniform3fv(U.uTint, S.tint); gl.uniform1f(U.uDensity, S.density);
    gl.uniform4fv(U.uWake, W.pos); gl.uniform2fv(U.uWakeDir, W.dir);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
};
if (gl) {
  initSky();
  sky.addEventListener('webglcontextlost', e => { e.preventDefault(); draw = () => {}; });
  sky.addEventListener('webglcontextrestored', initSky);
} else { sky.style.background = 'radial-gradient(ellipse at 50% 100%, #2a060b, #07090c 70%)'; }

// moving the pointer slices a short-lived wake through the fog (off under reduced motion)
addEventListener('pointermove', e => {
  S.mt = [(e.clientX - innerWidth/2)/innerHeight, -(e.clientY - innerHeight/2)/innerHeight];
  if (reduce) return;
  const [x, y] = S.mt, now = performance.now();
  if (!W.last) { W.last = { x, y }; return; }
  // samples at a fixed ~5px step along the path, all the same strength, so the wake looks
  // the same at any pointer speed; a still pointer adds nothing
  let dx = x - W.last.x, dy = y - W.last.y, dist = Math.hypot(dx, dy);
  if (dist < .006) return;
  dx /= dist; dy /= dist;
  for (; dist >= .006; dist -= .006) {
    W.last = { x:W.last.x + dx*.006, y:W.last.y + dy*.006 };
    W.trail.push({ x:W.last.x, y:W.last.y, dx, dy, born:now });
  }
  while (W.trail.length > 16) W.trail.shift();
}, {passive:true});
function updateWake(now){
  W.pos.fill(0); W.dir.fill(0);
  W.trail.forEach((s, i) => { W.pos.set([s.x, s.y, Math.exp(-(now - s.born)/700)*.9, 0], i*4); W.dir.set([s.dx, s.dy], i*2); });
}

/* ================= Bolt overlay ================= */
const bc = $('#bolt'), bx = bc.getContext('2d');
let bolts = [];
const sizeBolt = () => { const d = Math.min(devicePixelRatio||1, 2); bc.width = innerWidth*d; bc.height = innerHeight*d; bx.setTransform(d,0,0,d,0,0); };
sizeBolt(); addEventListener('resize', sizeBolt);
function path(x0,y0,x1,y1,disp,out){
  if (disp < 3) { out.push([x1,y1]); return; }
  const mx = (x0+x1)/2 + (Math.random()-.5)*disp, my = (y0+y1)/2 + (Math.random()-.5)*disp*.3;
  path(x0,y0,mx,my,disp/2,out); path(mx,my,x1,y1,disp/2,out);
}
function makeBolt(x, yEnd){
  const segs = []; const main = [[x + (Math.random()-.5)*160, -20]];
  path(main[0][0], -20, x, yEnd, 220, main); segs.push({pts:main, w:1.6});
  for (let i = 0; i < 3; i++) {
    const k = Math.floor(main.length*(.15 + Math.random()*.6)); const [sx,sy] = main[k];
    const br = [[sx,sy]]; path(sx, sy, sx + (Math.random()-.5)*300, sy + 80 + Math.random()*200, 90, br); segs.push({pts:br, w:1});
  }
  bolts.push({segs, born:performance.now()});
}
function drawBolts(now){
  bx.clearRect(0,0,innerWidth,innerHeight);
  bolts = bolts.filter(b => now - b.born < 700);
  for (const b of bolts) {
    const age = Math.max(0, (now - b.born)/700);
    const flick = (age < .12 || (age > .2 && age < .3) || (age > .38 && age < .45)) ? 1 : .25;
    const a = (1-age)*flick;
    for (const s of b.segs) {
      bx.beginPath(); s.pts.forEach(([x,y],i) => i ? bx.lineTo(x,y) : bx.moveTo(x,y));
      bx.strokeStyle = `rgba(255,190,200,${a*.22})`; bx.lineWidth = s.w*5; bx.shadowBlur = 18; bx.shadowColor = '#ff5a6e'; bx.stroke();
      bx.strokeStyle = `rgba(255,255,255,${a*.8})`; bx.lineWidth = s.w; bx.shadowBlur = 0; bx.stroke();
    }
  }
}

/* ================= Random lightning ================= */
// a strike lands somewhere across the sky every few seconds; sometimes a second one follows close behind
function strike(strong){
  if (reduce) return;
  const x = innerWidth*(.08 + Math.random()*.84);
  const near = strong || Math.random() < .4;
  S.flash = near ? .85 : .5;
  S.flicker = performance.now();
  const yEnd = innerHeight*(.45 + Math.random()*.4);
  S.strike = [(x - innerWidth/2)/innerHeight, .5 - yEnd*.5/innerHeight]; // light centred halfway down the bolt
  if (!reduce) makeBolt(x, yEnd);
}
let lightningTimeout, restrikeTimeout;
const schedule = () => {
  if (reduce) return;
  if (!document.hidden) { strike(); if (Math.random() < .3) restrikeTimeout = setTimeout(strike, 180 + Math.random()*420); }
  lightningTimeout = setTimeout(schedule, 3200 + Math.random()*5200);
};
if (!reduce) lightningTimeout = setTimeout(schedule, 1400);

/* ================= Stats count up once on load ================= */
document.querySelectorAll('.stats b').forEach((el, i) => {
  const to = +el.dataset.to, suf = el.dataset.suffix || '', unit = el.dataset.unit, t0 = performance.now() + 900 + i*120, D = reduce ? 1 : 1400;
  const put = v => { el.textContent = v.toLocaleString("en-US") + suf; if (unit) { const s = document.createElement('small'); s.textContent = unit; el.append(s); } };
  put(reduce ? to : 0);
  const tick = now => { const k = Math.min(1, Math.max(0, (now - t0)/D)), e = 1 - Math.pow(1 - k, 4); put(Math.round(to*e)); if (k < 1 && !reduce) requestAnimationFrame(tick); else if (reduce) put(to); };
  if (!reduce) requestAnimationFrame(tick);
  setTimeout(() => put(to), 900 + i*120 + D + 300); // lands on the real value even if animation frames are paused
});

/* ================= Main loop ================= */
const t0 = performance.now();
function frame(now){
  S.flash *= .93; // the glow lingers in the fog a moment after the bolt
  // the fog flickers with the bolt's own return strokes during its first half second
  const age = now - (S.flicker || -1e9);
  if (!reduce && age < 450 && Math.random() < .25) S.flash = Math.min(.9, S.flash + .2);
  updateWake(now);
  S.mouse[0] += (S.mt[0] - S.mouse[0]) * .05; S.mouse[1] += (S.mt[1] - S.mouse[1]) * .05;
  draw(reduce ? 12 : (now - t0)/1000);
  drawBolts(now);
  if (!reduce) frameId = requestAnimationFrame(frame);
}
let frameId = requestAnimationFrame(frame);
const redrawStaticSky = () => {
  if (reduce) {
    cancelAnimationFrame(frameId);
    frameId = requestAnimationFrame(frame);
  }
};
addEventListener('resize', redrawStaticSky);
sky.addEventListener('webglcontextrestored', redrawStaticSky);
motionPreference.addEventListener('change', event => {
  reduce = event.matches;
  clearTimeout(lightningTimeout);
  clearTimeout(restrikeTimeout);
  cancelAnimationFrame(frameId);
  bolts = [];
  S.flash = 0;
  frameId = requestAnimationFrame(frame);
  if (!reduce) lightningTimeout = setTimeout(schedule, 1400);
});
})();
