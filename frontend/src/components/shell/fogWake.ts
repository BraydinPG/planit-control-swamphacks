/**
 * The pointer's wake through the fog, as if a hand were drawn through a gas. The pointer
 * leaves a short trail; along it the fog parts sideways, is dragged slightly forward
 * and thins a little, then the gas closes back in as the trail fades (about a second).
 * Faster sweeps cut more clearly. All of it is deliberately subtle.
 *
 * Coordinates are the fog shader's: x and y in fractions of screen height, origin at the
 * centre, y up. public/landing.html carries a copy of this for the landing page.
 */
export const WAKE_POINTS = 16

/** GLSL: declares the uniforms and wake(p) -> vec3(displacement.xy, thinning 0-1). */
export const WAKE_GLSL = `
uniform vec4 uWake[${WAKE_POINTS}]; // xy position, z strength
uniform vec2 uWakeDir[${WAKE_POINTS}]; // unit direction of travel
vec3 wake(vec2 p){
  vec2 disp=vec2(0.);float cut=0.;
  for(int i=0;i<${WAKE_POINTS};i++){
    vec4 t=uWake[i];
    if(t.z<.001) continue;
    vec2 d=p-t.xy, v=uWakeDir[i], n=vec2(-v.y,v.x);
    float along=dot(d,v), across=dot(d,n);
    // a cursor-sized band along the path: about 0.8% of screen height wide (~14px across
    // at 900px tall), twice that long
    float k=exp(-across*across/.000064-along*along/.000256)*t.z;
    // parts smoothly to either side (zero on the path itself) and drags slightly forward
    disp+=(n*across*175.+v*.6)*k;
    cut+=k;
  }
  // Averaged over overlapping trail points, not summed, and kept to about 0.3% of screen
  // height: well below the band width, so the fog never folds over itself into rings.
  return vec3(disp*.003/max(1.,cut),clamp(cut,0.,1.));
}
`

type Sample = { x: number; y: number; dx: number; dy: number; speed: number; born: number }

export class FogWake {
  private trail: Sample[] = []
  private last: { x: number; y: number; t: number } | null = null
  readonly positions = new Float32Array(WAKE_POINTS * 4)
  readonly directions = new Float32Array(WAKE_POINTS * 2)

  /** Pointer position in screen pixels. */
  move(clientX: number, clientY: number, now: number) {
    const x = (clientX - window.innerWidth / 2) / window.innerHeight
    const y = -(clientY - window.innerHeight / 2) / window.innerHeight
    const last = this.last
    if (!last) {
      this.last = { x, y, t: now }
      return
    }
    const dx = x - last.x
    const dy = y - last.y
    const dist = Math.hypot(dx, dy)
    if (dist < 0.006) return // sample the path every ~0.6% of screen height (~5px)
    const seconds = Math.max(16, now - last.t) / 1000
    // fill in between far-apart pointer events so a fast flick leaves a line, not dots
    const steps = Math.ceil(dist / 0.01)
    for (let i = 1; i <= steps; i++)
      this.trail.push({ x: last.x + (dx * i) / steps, y: last.y + (dy * i) / steps, dx: dx / dist, dy: dy / dist, speed: dist / seconds, born: now })
    while (this.trail.length > WAKE_POINTS) this.trail.shift()
    this.last = { x, y, t: now }
  }

  /** Refreshes the uniform arrays for this frame. */
  update(now: number) {
    this.positions.fill(0)
    this.directions.fill(0)
    this.trail.forEach((s, i) => {
      const fade = Math.exp(-(now - s.born) / 700)
      const strength = Math.min(1, s.speed / 1.2) * fade * 0.9
      this.positions.set([s.x, s.y, strength, 0], i * 4)
      this.directions.set([s.dx, s.dy], i * 2)
    })
  }
}
