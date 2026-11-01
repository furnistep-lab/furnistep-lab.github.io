// FurniStep interactive 3D guide. Plays the video's own assembly animation (model.glb + guide3d.json exported by
// ytproject `python -m pipeline.web export`) step by step, with free orbit and zoom. No tracking, no third-party
// requests: three.js is bundled into assets/3d/viewer.js (see README, "3D guides").
import {
  ACESFilmicToneMapping,
  Color,
  DirectionalLight,
  HemisphereLight,
  MathUtils,
  PCFSoftShadowMap,
  PerspectiveCamera,
  PMREMGenerator,
  Scene,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const $ = (root, sel) => root.querySelector(sel);

function fmt(s) {
  s = Math.max(0, Math.floor(s + 1e-6));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}

// Camera samples of one shot: [t, px, py, pz, tx, ty, tz, lens], linear between samples.
function cameraAt(samples, t) {
  if (t <= samples[0][0]) return samples[0];
  for (let i = 1; i < samples.length; i++) {
    const b = samples[i];
    if (t <= b[0]) {
      const a = samples[i - 1];
      const k = b[0] > a[0] ? (t - a[0]) / (b[0] - a[0]) : 1;
      return a.map((v, j) => v + (b[j] - v) * k);
    }
  }
  return samples[samples.length - 1];
}

async function init(root) {
  const base = root.dataset.src.replace(/\/?$/, "/");
  const stage = $(root, ".v3d-stage");
  const status = $(root, ".v3d-status");
  const v = root.dataset.v ? "?v=" + encodeURIComponent(root.dataset.v) : "";
  const res = await fetch(base + "guide3d.json" + v);
  if (!res.ok) throw new Error("guide3d.json: HTTP " + res.status);
  const guide = await res.json();

  // ------------------------------------------------------------------ renderer, scene, lights
  const renderer = new WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFSoftShadowMap;
  renderer.domElement.setAttribute("aria-label", "3D view of the assembly. Drag to turn, scroll or pinch to zoom.");
  renderer.domElement.setAttribute("role", "img");
  stage.prepend(renderer.domElement);

  const scene = new Scene();
  scene.background = new Color(0xdfe4e8);
  const pmrem = new PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;
  scene.add(new HemisphereLight(0xffffff, 0x8a7560, 0.6));
  const sun = new DirectionalLight(0xfff4e6, 1.9);
  sun.position.set(-2.2, 3.6, 2.8);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -2, right: 2, top: 2, bottom: -2, near: 0.5, far: 9 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.01;
  scene.add(sun);

  const camera = new PerspectiveCamera(30, 16 / 9, 0.01, 60);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.12;
  controls.minDistance = 0.15;
  controls.maxDistance = 6;
  controls.maxPolarAngle = MathUtils.degToRad(88); // stay above the floor

  // ------------------------------------------------------------------ model and animation
  const gltf = await new GLTFLoader().loadAsync(base + guide.model + v, (ev) => {
    if (ev.total) status.textContent = "Loading 3D model… " + Math.round((100 * ev.loaded) / ev.total) + "%";
  });
  const model = gltf.scene;
  // glTF node extras land in userData; node names lose ':' and '.' (three.js track-name rules).
  let wall = null;
  model.traverse((o) => {
    if (o.userData.kind === "env" && o.userData.label === "wall") wall = o;
    if (!o.isMesh) return;
    const kind = o.userData.kind || (o.parent && o.parent.userData.kind);
    o.castShadow = kind !== "env";
    o.receiveShadow = true;
  });
  scene.add(model);

  // One evaluator per shot: every clip animates every node (translation, rotation, scale = visibility).
  const clips = Object.fromEntries(gltf.animations.map((c) => [c.name, c]));
  const shots = guide.shots.map((s) => {
    const clip = clips[s.id];
    const tracks = clip.tracks.map((tr) => {
      const [nodeName, prop] = [tr.name.slice(0, tr.name.lastIndexOf(".")), tr.name.slice(tr.name.lastIndexOf(".") + 1)];
      return { node: model.getObjectByName(nodeName), prop, interp: tr.createInterpolant() };
    });
    return { ...s, tracks };
  });
  const total = guide.duration_s;

  function pose(shot, t) {
    for (const tr of shot.tracks) {
      if (!tr.node) continue;
      const v = tr.interp.evaluate(t);
      if (tr.prop === "position") tr.node.position.fromArray(v);
      else if (tr.prop === "quaternion") tr.node.quaternion.fromArray(v);
      else if (tr.prop === "scale") {
        tr.node.scale.fromArray(v);
        tr.node.visible = v[0] > 0;
      }
    }
  }

  // Chapters: one per manual step (derived shots such as the turn-over before step 7 belong to their step) + "Done".
  const chapters = [];
  for (const s of shots) {
    const key = s.step || "done";
    let ch = chapters.find((c) => c.key === key);
    if (!ch) {
      const st = guide.steps.find((x) => x.n === s.step);
      ch = { key, n: s.step, start: s.start_s, end: s.start_s, text: st ? st.text : "Finished. Check that every screw is tight." };
      chapters.push(ch);
    }
    ch.end = s.start_s + s.duration_s;
  }

  // ------------------------------------------------------------------ UI
  const ui = {
    play: $(root, ".v3d-play"),
    prev: $(root, ".v3d-prev"),
    next: $(root, ".v3d-next"),
    follow: $(root, ".v3d-follow"),
    speed: $(root, ".v3d-speed"),
    full: $(root, ".v3d-full"),
    scrub: $(root, ".v3d-scrub"),
    time: $(root, ".v3d-time"),
    caption: $(root, ".v3d-caption"),
    ticks: $(root, ".v3d-ticks"),
    list: root.querySelectorAll("[data-v3d-step]"),
  };
  ui.scrub.max = String(total);
  chapters.forEach((c) => {
    const i = document.createElement("i");
    i.style.left = (100 * c.start) / total + "%";
    ui.ticks.appendChild(i);
  });

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const state = { t: 0, playing: !reduceMotion, follow: true, speed: 1, chapter: -1, visible: true };
  const tmpTarget = new Vector3();

  function chapterAt(t) {
    let k = 0;
    chapters.forEach((c, i) => {
      if (t >= c.start - 1e-6) k = i;
    });
    return k;
  }
  function shotAt(t) {
    for (const s of shots) if (t < s.start_s + s.duration_s) return s;
    return shots[shots.length - 1];
  }

  function setFollow(on) {
    state.follow = on;
    ui.follow.setAttribute("aria-pressed", String(on));
    ui.follow.classList.toggle("is-on", on);
  }
  function setPlaying(on) {
    if (on && state.t >= total - 1e-3) state.t = 0;
    state.playing = on;
    ui.play.setAttribute("aria-label", on ? "Pause" : "Play");
    root.classList.toggle("is-playing", on);
  }
  function seek(t) {
    state.t = Math.max(0, Math.min(total, t));
  }
  function goChapter(i) {
    i = Math.max(0, Math.min(chapters.length - 1, i));
    seek(chapters[i].start);
    setFollow(true);
  }

  function fitFov(lens) {
    // The video frames for a 36 mm wide sensor at 16:9. Keep that whole frame in view at any aspect ratio.
    // On tall screens a slightly tighter crop (the frame's outer edges are mostly floor) keeps the work readable.
    const crop = camera.aspect < 1.2 ? 0.8 : 1;
    const hfov = 2 * Math.atan((18 * crop) / lens);
    const vfov169 = 2 * Math.atan(Math.tan(hfov / 2) / (16 / 9));
    const vfov = camera.aspect >= 16 / 9 ? vfov169 : 2 * Math.atan(Math.tan(hfov / 2) / camera.aspect);
    return MathUtils.radToDeg(vfov);
  }

  function updateUI() {
    const k = chapterAt(state.t);
    if (k !== state.chapter) {
      state.chapter = k;
      const c = chapters[k];
      ui.caption.innerHTML = "";
      const b = document.createElement("strong");
      b.textContent = c.n ? "Step " + c.n + " of " + guide.steps.length : "Done";
      ui.caption.append(b, document.createTextNode(" " + c.text));
      ui.list.forEach((el) => {
        const on = el.dataset.v3dStep === String(c.n || "done");
        el.classList.toggle("is-current", on);
        el.setAttribute("aria-current", on ? "step" : "false");
      });
      ui.prev.disabled = k === 0;
      ui.next.disabled = k === chapters.length - 1;
    }
    ui.scrub.value = String(state.t);
    ui.scrub.style.setProperty("--p", (100 * state.t) / total + "%");
    ui.time.textContent = fmt(state.t) + " / " + fmt(total);
  }

  function resize() {
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(stage);
  resize();

  // ------------------------------------------------------------------ events
  ui.play.addEventListener("click", () => setPlaying(!state.playing));
  ui.prev.addEventListener("click", () => {
    const k = chapterAt(state.t);
    goChapter(state.t - chapters[k].start > 1.5 ? k : k - 1);
  });
  ui.next.addEventListener("click", () => goChapter(chapterAt(state.t) + 1));
  ui.follow.addEventListener("click", () => setFollow(!state.follow));
  ui.speed.addEventListener("click", () => {
    state.speed = state.speed === 1 ? 2 : state.speed === 2 ? 0.5 : 1;
    ui.speed.textContent = state.speed + "×";
  });
  ui.scrub.addEventListener("input", () => seek(parseFloat(ui.scrub.value)));
  ui.list.forEach((el) =>
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      const key = el.dataset.v3dStep;
      goChapter(chapters.findIndex((c) => String(c.n || "done") === key));
      setPlaying(true);
      history.replaceState(null, "", el.getAttribute("href"));
      stage.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
    }),
  );
  controls.addEventListener("start", () => setFollow(false)); // the visitor takes the camera
  ui.full.addEventListener("click", () => {
    const fs = document.fullscreenElement;
    if (fs) document.exitFullscreen();
    else if (root.requestFullscreen) root.requestFullscreen().catch(() => root.classList.toggle("is-max"));
    else root.classList.toggle("is-max");
  });
  root.addEventListener("keydown", (ev) => {
    if (ev.target.closest("input")) return;
    if (ev.key === " " || ev.key === "k") setPlaying(!state.playing);
    else if (ev.key === "ArrowRight" || ev.key === "n") goChapter(chapterAt(state.t) + 1);
    else if (ev.key === "ArrowLeft" || ev.key === "p") goChapter(chapterAt(state.t) - 1);
    else if (ev.key === "c") setFollow(!state.follow);
    else return;
    ev.preventDefault();
  });
  new IntersectionObserver((es) => (state.visible = es[0].isIntersecting)).observe(stage);

  // ------------------------------------------------------------------ loop
  let last = performance.now();
  function frame(now) {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    if (state.visible && !document.hidden) {
      if (state.playing) {
        seek(state.t + dt * state.speed);
        if (state.t >= total) setPlaying(false);
      }
      const shot = shotAt(state.t);
      const lt = Math.min(state.t - shot.start_s, shot.duration_s);
      pose(shot, lt);
      if (state.follow) {
        const c = cameraAt(shot.camera, lt);
        camera.position.set(c[1], c[2], c[3]);
        tmpTarget.set(c[4], c[5], c[6]);
        controls.target.copy(tmpTarget);
        camera.fov = fitFov(c[7]);
        camera.updateProjectionMatrix();
        camera.lookAt(tmpTarget);
      } else {
        controls.update();
      }
      // The wall stands behind the product: hide it when the visitor looks from behind it.
      if (wall && guide.wall_z_m != null) wall.visible = wall.visible && camera.position.z > guide.wall_z_m + 0.05;
      renderer.render(scene, camera);
      updateUI();
    }
    requestAnimationFrame(frame);
  }
  // Deep links from the guide page: #step-3 starts at step 3, #done at the finished product.
  function fromHash() {
    const m = /^#(?:step-(\d+)|(done))$/.exec(location.hash);
    if (!m) return false;
    const i = chapters.findIndex((c) => (m[2] ? !c.n : c.n === Number(m[1])));
    if (i < 0) return false;
    goChapter(i);
    return true;
  }
  window.addEventListener("hashchange", fromHash);
  fromHash();
  setFollow(true);
  setPlaying(state.playing);
  status.hidden = true;
  root.classList.add("is-ready");
  requestAnimationFrame(frame);
}

document.querySelectorAll(".v3d[data-src]").forEach((root) => {
  init(root).catch((err) => {
    console.error(err);
    const s = $(root, ".v3d-status");
    s.hidden = false;
    s.textContent = "Sorry, the 3D view could not load in this browser. The written steps below still work.";
    root.classList.add("is-error");
  });
});
