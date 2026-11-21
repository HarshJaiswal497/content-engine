// ---- background: moving gradient + water ripples (three.js) ----
(function () {
  const cv = document.getElementById("gl");
  const R = new THREE.WebGLRenderer({ canvas: cv, antialias: false, preserveDrawingBuffer: true });
  R.setPixelRatio(1); R.setSize(540, 960, false);
  const sc = new THREE.Scene(), cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const imp = []; for (let i = 0; i < 16; i++) imp.push(new THREE.Vector4(0, 0, 0, 0));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uImp: { value: imp } },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }",
    fragmentShader: `
      precision highp float; varying vec2 vUv; uniform float uTime; uniform vec4 uImp[16];
      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
        return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }
      void main(){
        const float A = 0.5625; vec2 uv = vUv; vec2 disp = vec2(0.); float glow = 0.;
        for (int i = 0; i < 16; i++) {
          vec4 im = uImp[i];
          if (im.w > 0.) {
            float age = uTime - im.z;
            if (age > 0. && age < 3.2) {
              vec2 d2 = (uv - im.xy) * vec2(A, 1.); float d = length(d2);
              float r = age * .72, w = d - r;
              float env = exp(-age * 1.15) * im.w;
              float pack = exp(-pow(w * 6., 2.));
              float wave = sin(w * 52.) * pack;
              disp += d2 / (d + 1e-4) * wave * .020 * env;
              glow += (exp(-pow(w * 16., 2.)) * .8 + max(wave, 0.) * .45) * env * smoothstep(0., .05, age);
            }
          }
        }
        vec2 q = uv + disp; vec2 qa = vec2(q.x * A, q.y);
        float t = uTime * .22;
        vec3 c = vec3(.040, .024, .022);
        vec2 b1 = vec2(.30 + .22 * sin(t * 1.3), .72 + .14 * cos(t * 1.1));
        vec2 b2 = vec2(.74 + .20 * cos(t * .9 + 1.), .46 + .20 * sin(t * 1.2));
        vec2 b3 = vec2(.50 + .26 * sin(t * .7 + 2.), .22 + .12 * cos(t * 1.5));
        c += vec3(.46, .19, .06) * exp(-5.0 * length(qa - b1 * vec2(A, 1.)));
        c += vec3(.30, .12, .05) * exp(-4.0 * length(qa - b2 * vec2(A, 1.)));
        c += vec3(.20, .08, .04) * exp(-3.5 * length(qa - b3 * vec2(A, 1.)));
        float n = noise(qa * 5. + t * 1.5) * .5 + noise(qa * 11. - t) * .25;
        c *= .86 + n * .22;
        c += vec3(1., .56, .26) * glow * .26;
        gl_FragColor = vec4(c, 1.);
      }`
  });
  sc.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat));
  const impList = () => { IMP.slice(0, 16).forEach((a, i) => imp[i].set(a[0], a[1], a[2], a[3])); };
  function renderAt(t) { mat.uniforms.uTime.value = t; R.render(sc, cam); }
  window.__glInit = () => { impList(); renderAt(0); };
  window.addEventListener("hf-seek", (e) => { renderAt(e.detail.time); });
  window.__glInit();
})();
window.__timelines["main"] = tl;
