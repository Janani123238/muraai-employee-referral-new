/* =========================================================================
   Hero 3D Particle Network — Three.js
   Premium connected-network animation for the hero section.
   Navy Blue / Teal / Sky corporate palette.
   ========================================================================= */

let hero3dScene, hero3dCamera, hero3dRenderer, hero3dParticles, hero3dHubParticles;
let hero3dLines, hero3dAnimId, hero3dMouse = {x:0, y:0};
let hero3dInited = false;

function initHero3D(){
  if(hero3dInited) return;
  if(typeof THREE === 'undefined') return;

  const canvas = document.getElementById('hero3dCanvas');
  if(!canvas) return;

  /* Respect reduced motion */
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    canvas.style.display = 'none';
    return;
  }

  hero3dInited = true;
  const container = canvas.parentElement;
  const W = container.clientWidth;
  const H = container.clientHeight;

  /* Scene */
  hero3dScene = new THREE.Scene();

  /* Camera — wider FOV for depth */
  hero3dCamera = new THREE.PerspectiveCamera(55, W / H, 0.1, 1000);
  hero3dCamera.position.set(0, 0, 50);

  /* Renderer */
  hero3dRenderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: false,
    powerPreference: 'high-performance',
  });
  hero3dRenderer.setSize(W, H);
  hero3dRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  hero3dRenderer.setClearColor(0x000000, 0);

  /* Adaptive particle count */
  const isMobile = /Mobi|Android/i.test(navigator.userAgent) || W < 768;
  const PARTICLE_COUNT = isMobile ? 45 : 90;
  const HUB_COUNT = isMobile ? 4 : 7;
  const CONNECTION_DIST = isMobile ? 14 : 18;

  /* ---- Particle positions & colors ---- */
  const positions = new Float32Array(PARTICLE_COUNT * 3);
  const colors = new Float32Array(PARTICLE_COUNT * 3);
  const sizes = new Float32Array(PARTICLE_COUNT);
  const velocities = [];

  const palette = [
    new THREE.Color(0x38BDF8),  /* sky blue */
    new THREE.Color(0x60A5FA),  /* light blue */
    new THREE.Color(0x2DD4BF),  /* teal */
    new THREE.Color(0x5EEAD4),  /* light teal */
    new THREE.Color(0x93C5FD),  /* soft blue */
    new THREE.Color(0xFFFFFF),  /* white */
  ];

  for(let i = 0; i < PARTICLE_COUNT; i++){
    const i3 = i * 3;
    positions[i3]     = (Math.random() - 0.5) * 80;
    positions[i3 + 1] = (Math.random() - 0.5) * 50;
    positions[i3 + 2] = (Math.random() - 0.5) * 40;

    const c = palette[Math.floor(Math.random() * palette.length)];
    colors[i3]     = c.r;
    colors[i3 + 1] = c.g;
    colors[i3 + 2] = c.b;

    sizes[i] = Math.random() * 2.0 + 0.8;

    velocities.push({
      x: (Math.random() - 0.5) * 0.008,
      y: (Math.random() - 0.5) * 0.008,
      z: (Math.random() - 0.5) * 0.004,
      phase: Math.random() * Math.PI * 2,
    });
  }

  /* Particles geometry */
  const particleGeom = new THREE.BufferGeometry();
  particleGeom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particleGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  particleGeom.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

  /* Custom shader material for soft glowing particles */
  const particleMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    },
    vertexShader: `
      attribute float size;
      attribute vec3 color;
      varying vec3 vColor;
      varying float vAlpha;
      uniform float uTime;
      uniform float uPixelRatio;
      void main(){
        vColor = color;
        vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
        float dist = length(mvPos.xyz);
        vAlpha = smoothstep(80.0, 10.0, dist) * 0.85;
        gl_PointSize = size * uPixelRatio * (35.0 / -mvPos.z);
        gl_Position = projectionMatrix * mvPos;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      void main(){
        float d = length(gl_PointCoord - vec2(0.5));
        if(d > 0.5) discard;
        float glow = 1.0 - smoothstep(0.0, 0.5, d);
        glow = pow(glow, 1.5);
        gl_FragColor = vec4(vColor, glow * vAlpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  hero3dParticles = new THREE.Points(particleGeom, particleMat);
  hero3dScene.add(hero3dParticles);

  /* ---- Hub particles (larger, brighter) ---- */
  const hubPositions = new Float32Array(HUB_COUNT * 3);
  const hubColors = new Float32Array(HUB_COUNT * 3);
  const hubSizes = new Float32Array(HUB_COUNT);
  const hubVelocities = [];

  for(let i = 0; i < HUB_COUNT; i++){
    const i3 = i * 3;
    hubPositions[i3]     = (Math.random() - 0.5) * 60;
    hubPositions[i3 + 1] = (Math.random() - 0.5) * 35;
    hubPositions[i3 + 2] = (Math.random() - 0.5) * 20;

    const hubColor = i % 2 === 0
      ? new THREE.Color(0x38BDF8)
      : new THREE.Color(0x2DD4BF);
    hubColors[i3]     = hubColor.r;
    hubColors[i3 + 1] = hubColor.g;
    hubColors[i3 + 2] = hubColor.b;

    hubSizes[i] = Math.random() * 4.0 + 3.0;

    hubVelocities.push({
      x: (Math.random() - 0.5) * 0.005,
      y: (Math.random() - 0.5) * 0.005,
      z: (Math.random() - 0.5) * 0.003,
    });
  }

  const hubGeom = new THREE.BufferGeometry();
  hubGeom.setAttribute('position', new THREE.BufferAttribute(hubPositions, 3));
  hubGeom.setAttribute('color', new THREE.BufferAttribute(hubColors, 3));
  hubGeom.setAttribute('size', new THREE.BufferAttribute(hubSizes, 1));

  const hubMat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    },
    vertexShader: `
      attribute float size;
      attribute vec3 color;
      varying vec3 vColor;
      varying float vAlpha;
      uniform float uTime;
      uniform float uPixelRatio;
      void main(){
        vColor = color;
        vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
        float pulse = 0.7 + 0.3 * sin(uTime * 0.8 + position.x * 0.1);
        vAlpha = pulse * smoothstep(100.0, 10.0, length(mvPos.xyz));
        gl_PointSize = size * uPixelRatio * (45.0 / -mvPos.z);
        gl_Position = projectionMatrix * mvPos;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      void main(){
        float d = length(gl_PointCoord - vec2(0.5));
        if(d > 0.5) discard;
        float glow = 1.0 - smoothstep(0.0, 0.5, d);
        glow = pow(glow, 1.2);
        float ring = smoothstep(0.35, 0.4, d) * (1.0 - smoothstep(0.45, 0.5, d)) * 0.4;
        gl_FragColor = vec4(vColor, (glow + ring) * vAlpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  hero3dHubParticles = new THREE.Points(hubGeom, hubMat);
  hero3dScene.add(hero3dHubParticles);

  /* ---- Connection lines ---- */
  const maxLines = PARTICLE_COUNT * 4;
  const linePositions = new Float32Array(maxLines * 6);
  const lineColors = new Float32Array(maxLines * 6);

  const lineGeom = new THREE.BufferGeometry();
  lineGeom.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  lineGeom.setAttribute('color', new THREE.BufferAttribute(lineColors, 3));
  lineGeom.setDrawRange(0, 0);

  const lineMat = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 1,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  hero3dLines = new THREE.LineSegments(lineGeom, lineMat);
  hero3dScene.add(hero3dLines);

  /* ---- Ambient light ring (subtle depth cue) ---- */
  const ringGeom = new THREE.RingGeometry(28, 28.3, 64);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x1E40AF,
    transparent: true,
    opacity: 0.06,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  });
  const ring = new THREE.Mesh(ringGeom, ringMat);
  ring.rotation.x = Math.PI / 2.5;
  hero3dScene.add(ring);

  const ring2Geom = new THREE.RingGeometry(38, 38.2, 64);
  const ring2Mat = new THREE.MeshBasicMaterial({
    color: 0x38BDF8,
    transparent: true,
    opacity: 0.04,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  });
  const ring2 = new THREE.Mesh(ring2Geom, ring2Mat);
  ring2.rotation.x = Math.PI / 3;
  ring2.rotation.z = Math.PI / 6;
  hero3dScene.add(ring2);

  /* ---- Mouse parallax ---- */
  document.addEventListener('mousemove', function(e){
    hero3dMouse.x = (e.clientX / window.innerWidth - 0.5) * 2;
    hero3dMouse.y = -(e.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  /* ---- Animation loop ---- */
  let time = 0;
  const clock = new THREE.Clock();

  function animate(){
    hero3dAnimId = requestAnimationFrame(animate);
    const dt = clock.getDelta();
    time += dt;

    /* Update particle positions */
    const pos = particleGeom.attributes.position.array;
    for(let i = 0; i < PARTICLE_COUNT; i++){
      const i3 = i * 3;
      const v = velocities[i];
      pos[i3]     += v.x + Math.sin(time * 0.3 + v.phase) * 0.003;
      pos[i3 + 1] += v.y + Math.cos(time * 0.25 + v.phase) * 0.003;
      pos[i3 + 2] += v.z + Math.sin(time * 0.2 + v.phase) * 0.002;

      /* Soft boundary wrap */
      if(pos[i3] > 42) pos[i3] = -42;
      if(pos[i3] < -42) pos[i3] = 42;
      if(pos[i3 + 1] > 28) pos[i3 + 1] = -28;
      if(pos[i3 + 1] < -28) pos[i3 + 1] = 28;
      if(pos[i3 + 2] > 22) pos[i3 + 2] = -22;
      if(pos[i3 + 2] < -22) pos[i3 + 2] = 22;
    }
    particleGeom.attributes.position.needsUpdate = true;

    /* Update hub positions */
    const hPos = hubGeom.attributes.position.array;
    for(let i = 0; i < HUB_COUNT; i++){
      const i3 = i * 3;
      const hv = hubVelocities[i];
      hPos[i3]     += hv.x;
      hPos[i3 + 1] += hv.y;
      hPos[i3 + 2] += hv.z;
      if(hPos[i3] > 32) hv.x *= -1;
      if(hPos[i3] < -32) hv.x *= -1;
      if(hPos[i3 + 1] > 20) hv.y *= -1;
      if(hPos[i3 + 1] < -20) hv.y *= -1;
    }
    hubGeom.attributes.position.needsUpdate = true;

    /* Update connection lines */
    let lineIdx = 0;
    const lPos = lineGeom.attributes.position.array;
    const lCol = lineGeom.attributes.color.array;
    for(let i = 0; i < PARTICLE_COUNT && lineIdx < maxLines; i++){
      for(let j = i + 1; j < PARTICLE_COUNT && lineIdx < maxLines; j++){
        const i3 = i * 3, j3 = j * 3;
        const dx = pos[i3] - pos[j3];
        const dy = pos[i3+1] - pos[j3+1];
        const dz = pos[i3+2] - pos[j3+2];
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if(dist < CONNECTION_DIST){
          const alpha = 1.0 - dist / CONNECTION_DIST;
          const l6 = lineIdx * 6;
          lPos[l6]   = pos[i3];   lPos[l6+1] = pos[i3+1]; lPos[l6+2] = pos[i3+2];
          lPos[l6+3] = pos[j3];   lPos[l6+4] = pos[j3+1]; lPos[l6+5] = pos[j3+2];
          lCol[l6] = 0.22 * alpha; lCol[l6+1] = 0.48 * alpha; lCol[l6+2] = 0.72 * alpha;
          lCol[l6+3] = 0.22 * alpha; lCol[l6+4] = 0.48 * alpha; lCol[l6+5] = 0.72 * alpha;
          lineIdx++;
        }
      }
    }
    lineGeom.setDrawRange(0, lineIdx * 2);
    lineGeom.attributes.position.needsUpdate = true;
    lineGeom.attributes.color.needsUpdate = true;

    /* Update shader time uniforms */
    particleMat.uniforms.uTime.value = time;
    hubMat.uniforms.uTime.value = time;

    /* Camera follows mouse with damping */
    hero3dCamera.position.x += (hero3dMouse.x * 3 - hero3dCamera.position.x) * 0.02;
    hero3dCamera.position.y += (hero3dMouse.y * 2 - hero3dCamera.position.y) * 0.02;
    hero3dCamera.lookAt(0, 0, 0);

    /* Slow auto-rotation */
    hero3dScene.rotation.y = Math.sin(time * 0.05) * 0.08;
    hero3dScene.rotation.x = Math.cos(time * 0.04) * 0.03;

    /* Subtle ring rotation */
    ring.rotation.z = time * 0.02;
    ring2.rotation.z = -time * 0.015;

    hero3dRenderer.render(hero3dScene, hero3dCamera);
  }

  animate();

  /* ---- Resize handler ---- */
  function onResize(){
    const c = document.getElementById('hero3dCanvas');
    if(!c) return;
    const par = c.parentElement;
    if(!par) return;
    const w = par.clientWidth;
    const h = par.clientHeight;
    hero3dCamera.aspect = w / h;
    hero3dCamera.updateProjectionMatrix();
    hero3dRenderer.setSize(w, h);
    hero3dRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  }

  window.addEventListener('resize', onResize, { passive: true });

  /* ---- Pause when hero not visible ---- */
  const heroObserver = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(entry.isIntersecting){
        if(!hero3dAnimId) animate();
      } else {
        if(hero3dAnimId){
          cancelAnimationFrame(hero3dAnimId);
          hero3dAnimId = null;
        }
      }
    });
  }, { threshold: 0.1 });

  const heroEl = document.getElementById('hero');
  if(heroEl) heroObserver.observe(heroEl);
}

/* Cleanup when leaving landing page */
function destroyHero3D(){
  if(hero3dAnimId){
    cancelAnimationFrame(hero3dAnimId);
    hero3dAnimId = null;
  }
  hero3dInited = false;
  if(hero3dRenderer){
    hero3dRenderer.dispose();
    hero3dRenderer = null;
  }
  if(hero3dScene){
    hero3dScene.traverse(function(obj){
      if(obj.geometry) obj.geometry.dispose();
      if(obj.material){
        if(Array.isArray(obj.material)) obj.material.forEach(function(m){ m.dispose(); });
        else obj.material.dispose();
      }
    });
    hero3dScene = null;
  }
  hero3dCamera = null;
}
