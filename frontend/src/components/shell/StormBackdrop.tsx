import { useEffect, useRef } from 'react'
import { isVivid, onStormLevel } from './stormLevel'
import { FogWake, WAKE_GLSL } from './fogWake'

/**
 * Dark red fog with random lightning behind every app page, matching the landing
 * page (public/landing.html). App pages use the vivid level (useVividStorm); the
 * sign-in and loading screens stay calm.
 *
 * Legibility: the fog colour is clamped in the shader (see the cap in FRAGMENT) so
 * text that sits directly on the page stays at 4.5:1 or better, including
 * mid-flash, and red alert surfaces stay distinct from it.
 * Bolts are drawn dim and only for 0.7 s. Cards keep their own opaque surfaces.
 * The layer sits behind all content (z-index -1), takes no pointer events and is
 * hidden from assistive technology. Reduced motion shows a still fog, no lightning.
 */
const VERTEX = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}'
const FRAGMENT = `precision mediump float;
uniform vec2 uRes;uniform float uTime;uniform float uFlash;uniform vec2 uStrike;uniform float uLevel;
${WAKE_GLSL}
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;mat2 m=mat2(1.6,1.2,-1.2,1.6);for(int i=0;i<5;i++){v+=a*n(p);p=m*p;a*=.5;}return v;}
void main(){
  vec2 uv=gl_FragCoord.xy/uRes;
  vec2 p=(gl_FragCoord.xy-.5*uRes)/uRes.y;
  float t=uTime*.025;
  // the pointer's wake: the gas parts along its path, then closes back in (no darkening)
  vec3 wk=wake(p);
  vec2 cp=(p-wk.xy)*vec2(.8,1.3);
  vec2 q=vec2(fbm(cp*1.3+vec2(t,0.)),fbm(cp*1.3+vec2(5.2,1.3)-t));
  vec2 r=vec2(fbm(cp*1.3+3.2*q+vec2(1.7,9.2)+t*1.4),fbm(cp*1.3+3.2*q+vec2(8.3,2.8)-t*1.1));
  float f=fbm(cp*1.1+3.*r);
  float fog=smoothstep(.2,.95,f)*(.55+.6*(1.-uv.y*.6))*1.25;
  float edge=smoothstep(.45,.75,f)-smoothstep(.75,1.,f);
  vec3 tint=vec3(.95,.12,.16);
  // base matches the app background (#121214) so plain areas look unchanged at rest
  // uLevel 0 = calm (sign-in and loading screens), 1 = vivid (app pages)
  vec3 col=mix(vec3(.071,.071,.078),mix(vec3(.11,.04,.045),vec3(.24,.06,.07),uLevel),fog);
  col+=tint*edge*mix(.012,.05,uLevel);
  float d=length(p-uStrike);
  float lit=uFlash*(exp(-d*1.5)*1.5+.12)*(.02+fog*1.1+edge*.8);
  col+=mix(tint,vec3(1.,.8,.84),.4)*lit*mix(.32,.6,uLevel);
  col*=1.-.45*pow(length(uv-.5)*1.25,2.2);
  // Cap, even mid-flash. Calm: rgb(.20,.06,.065), about (51,15,17). Vivid: rgb(.34,.09,.10),
  // about (87,23,26), relative luminance ~0.027. At the vivid cap, the text tokens that sit
  // directly on the page stay at 4.5:1 or better (muted ~5.3, link ~5.2, stop-text ~4.9,
  // sim ~4.8), and the fog stays far darker than the stop-work red (#c0262d).
  col=min(col,mix(vec3(.20,.06,.065),vec3(.34,.09,.10),uLevel));
  gl_FragColor=vec4(max(col,0.),1.);
}`

export function StormBackdrop() {
  const sky = useRef<HTMLCanvasElement>(null)
  const bolt = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const skyEl = sky.current
    const boltEl = bolt.current
    if (!skyEl || !boltEl) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const gl = skyEl.getContext('webgl', { antialias: false })
    const bx = boltEl.getContext('2d')
    const state = {
      flash: 0,
      strike: [0, 0.3] as [number, number],
      flicker: -1e9,
      level: isVivid() ? 1 : 0,
    }
    // the pointer's wake through the fog (empty, so no effect, under reduced motion)
    const wake = new FogWake()
    let draw: (time: number) => void = () => {}
    let raf = 0
    let timer = 0
    const cleanups: (() => void)[] = []

    if (gl) {
      const shader = (type: number, src: string) => {
        const s = gl.createShader(type)!
        gl.shaderSource(s, src)
        gl.compileShader(s)
        return s
      }
      const program = gl.createProgram()!
      gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX))
      gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT))
      gl.linkProgram(program)
      gl.useProgram(program)
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer())
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
      const loc = gl.getAttribLocation(program, 'p')
      gl.enableVertexAttribArray(loc)
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)
      const u = (name: string) => gl.getUniformLocation(program, name)
      const uRes = u('uRes'), uTime = u('uTime'), uFlash = u('uFlash'), uStrike = u('uStrike'), uLevel = u('uLevel'), uWake = u('uWake'), uWakeDir = u('uWakeDir')
      // low resolution: the fog is soft anyway, and field phones save battery
      const size = () => {
        skyEl.width = Math.max(1, Math.round(window.innerWidth * 0.35))
        skyEl.height = Math.max(1, Math.round(window.innerHeight * 0.35))
        gl.viewport(0, 0, skyEl.width, skyEl.height)
      }
      size()
      window.addEventListener('resize', size)
      cleanups.push(() => window.removeEventListener('resize', size))
      draw = (time) => {
        gl.uniform2f(uRes, skyEl.width, skyEl.height)
        gl.uniform1f(uTime, time)
        gl.uniform1f(uFlash, state.flash)
        gl.uniform2f(uStrike, state.strike[0], state.strike[1])
        gl.uniform1f(uLevel, state.level)
        gl.uniform4fv(uWake, wake.positions)
        gl.uniform2fv(uWakeDir, wake.directions)
        gl.drawArrays(gl.TRIANGLES, 0, 3)
      }
    } else {
      skyEl.style.background = 'radial-gradient(ellipse at 50% 100%, #26090d, #121214 70%)'
    }

    if (reduce) {
      // still fog, redrawn only when the level changes
      const still = () => {
        state.level = isVivid() ? 1 : 0
        draw(12)
      }
      still()
      const stopListening = onStormLevel(still)
      return () => {
        stopListening()
        cleanups.forEach((fn) => fn())
      }
    }

    // bolts: a jagged main channel with a few branches, drawn dim and briefly
    type Bolt = { segs: { pts: [number, number][]; w: number }[]; born: number }
    let bolts: Bolt[] = []
    const sizeBolt = () => {
      if (!bx) return
      const d = Math.min(window.devicePixelRatio || 1, 2)
      boltEl.width = window.innerWidth * d
      boltEl.height = window.innerHeight * d
      bx.setTransform(d, 0, 0, d, 0, 0)
    }
    sizeBolt()
    window.addEventListener('resize', sizeBolt)
    cleanups.push(() => window.removeEventListener('resize', sizeBolt))
    const path = (x0: number, y0: number, x1: number, y1: number, disp: number, out: [number, number][]) => {
      if (disp < 3) {
        out.push([x1, y1])
        return
      }
      const mx = (x0 + x1) / 2 + (Math.random() - 0.5) * disp
      const my = (y0 + y1) / 2 + (Math.random() - 0.5) * disp * 0.3
      path(x0, y0, mx, my, disp / 2, out)
      path(mx, my, x1, y1, disp / 2, out)
    }
    const makeBolt = (x: number, yEnd: number) => {
      const main: [number, number][] = [[x + (Math.random() - 0.5) * 160, -20]]
      path(main[0][0], -20, x, yEnd, 220, main)
      const segs = [{ pts: main, w: 1.4 }]
      for (let i = 0; i < 2; i++) {
        const [sx, sy] = main[Math.floor(main.length * (0.15 + Math.random() * 0.6))]
        const br: [number, number][] = [[sx, sy]]
        path(sx, sy, sx + (Math.random() - 0.5) * 300, sy + 80 + Math.random() * 200, 90, br)
        segs.push({ pts: br, w: 0.9 })
      }
      bolts.push({ segs, born: performance.now() })
    }
    const drawBolts = (now: number) => {
      if (!bx) return
      bx.clearRect(0, 0, window.innerWidth, window.innerHeight)
      bolts = bolts.filter((b) => now - b.born < 700)
      for (const b of bolts) {
        const age = (now - b.born) / 700
        const flick = age < 0.12 || (age > 0.2 && age < 0.3) ? 1 : 0.3
        const a = (1 - age) * flick
        for (const s of b.segs) {
          bx.beginPath()
          s.pts.forEach(([x, y], i) => (i ? bx.lineTo(x, y) : bx.moveTo(x, y)))
          bx.strokeStyle = `rgba(255,140,150,${a * 0.1})`
          bx.lineWidth = s.w * 4
          bx.stroke()
          bx.strokeStyle = `rgba(255,225,230,${a * (0.3 + 0.1 * state.level)})`
          bx.lineWidth = s.w
          bx.stroke()
        }
      }
    }
    const strike = () => {
      const x = window.innerWidth * (0.08 + Math.random() * 0.84)
      const yEnd = window.innerHeight * (0.4 + Math.random() * 0.4)
      state.flash = (isVivid() ? 0.6 : 0.45) + Math.random() * 0.3
      state.flicker = performance.now()
      state.strike = [(x - window.innerWidth / 2) / window.innerHeight, 0.5 - (yEnd * 0.5) / window.innerHeight]
      makeBolt(x, yEnd)
    }
    // Random timing. App pages: every 2.5–8 s, sometimes with a quick second strike.
    // Sign-in and loading screens stay calm: every 6–16 s.
    let follow = 0
    const schedule = () => {
      if (!document.hidden) {
        strike()
        if (isVivid() && Math.random() < 0.3) follow = window.setTimeout(strike, 150 + Math.random() * 400)
      }
      timer = window.setTimeout(schedule, isVivid() ? 2500 + Math.random() * 5500 : 6000 + Math.random() * 10000)
    }
    timer = window.setTimeout(schedule, 2500)

    // the pointer slices a short-lived wake through the fog (see fogWake.ts)
    const onPointer = (event: PointerEvent) => wake.move(event.clientX, event.clientY, performance.now())
    window.addEventListener('pointermove', onPointer, { passive: true })
    cleanups.push(() => window.removeEventListener('pointermove', onPointer))

    const t0 = performance.now()
    let last = 0
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (now - last < 33) return // about 30 frames a second is plenty for fog
      last = now
      state.level += ((isVivid() ? 1 : 0) - state.level) * 0.05 // fades between levels
      state.flash *= 0.88
      wake.update(now)
      if (now - state.flicker < 400 && Math.random() < 0.2) state.flash = Math.min(0.9, state.flash + 0.15)
      draw((now - t0) / 1000)
      drawBolts(now)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(timer)
      window.clearTimeout(follow)
      cleanups.forEach((fn) => fn())
    }
  }, [])

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 bg-bg">
      <canvas ref={sky} className="absolute inset-0 block size-full" />
      <canvas ref={bolt} className="absolute inset-0 block size-full mix-blend-screen" />
    </div>
  )
}
