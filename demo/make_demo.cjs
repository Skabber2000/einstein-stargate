#!/usr/bin/env node
// Pipeline: generate per-scene TTS → record Playwright walkthrough timed to TTS → mux to mp4.
// Requirements: macOS `say`, ffmpeg, ffprobe, playwright (already installed globally).

const { chromium } = require('/Users/e.nayshtetik/.local/share/node/lib/node_modules/playwright');
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname);
const OUT  = path.join(ROOT, 'build');
fs.mkdirSync(OUT, { recursive: true });

// Language suffix: empty for English, '_uk' / '_es' / ... otherwise.
// Block WAVs:    block_NN.wav (en)  |  block_uk_NN.wav (uk) ...
// Outputs:       spacetime_demo[_uk].mp4 etc.
const LANG = (process.env.LANG || 'en').replace(/[^a-z]/g, '').slice(0, 4);
const SUFFIX  = LANG === 'en' ? '' : `_${LANG}`;
const BPREFIX = LANG === 'en' ? '' : `${LANG}_`;
console.log(`[lang] ${LANG}  blocks=block_${BPREFIX}NN.wav  out=spacetime_demo${SUFFIX}.mp4`);

const SCRIPT = JSON.parse(fs.readFileSync(path.join(ROOT, 'script.json'), 'utf8'));
const PROJECT_ROOT = path.resolve(ROOT, '..');
// Piper model path is relative to project root in script.json
const MODEL_PATH = path.resolve(PROJECT_ROOT, SCRIPT.model);
const PIPER_BIN  = path.resolve(PROJECT_ROOT, '.venv', 'bin', 'piper');
const LENGTH_SCALE = String(SCRIPT.length_scale ?? 1.0);

// Reduce key to a safe filename component (path-traversal-proof).
const safeKey = (k) => String(k).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 32) || 'block';

// ffprobe via argv (no shell, no template).
const probe = (file) => {
  const r = spawnSync('ffprobe',
    ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', file],
    { encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`ffprobe failed: ${r.stderr}`);
  return parseFloat(r.stdout.trim());
};

// ── 1. Synthesize TTS per scene block ─────────────────────────────────
console.log('[1/4] Generating TTS…');
const blocks = [];
SCRIPT.scenes.forEach((s, i) => {
  // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
  const wav = path.join(OUT, `block_${BPREFIX}${String(i).padStart(2,'0')}.wav`);

  if (SCRIPT.engine === 'f5-tts') {
    // Pre-rendered by demo/synthesize.py — no synthesis here, just probe.
    if (!fs.existsSync(wav)) {
      throw new Error(`F5-TTS WAV missing: ${wav}\nRun: python demo/synthesize.py`);
    }
  } else {
    // Piper fallback: synthesize text → WAV
    const text = s.lines.join(' ');
    // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
    const rawWav = path.join(OUT, `block_${String(i).padStart(2,'0')}_raw.wav`);
    const r = spawnSync(PIPER_BIN, [
      '--model', MODEL_PATH, '--length_scale', LENGTH_SCALE, '--output_file', rawWav,
    ], { input: text, stdio: ['pipe', 'ignore', 'inherit'] });
    if (r.status !== 0) throw new Error(`piper failed (exit ${r.status}) on block ${i}`);
    spawnSync('ffmpeg', ['-y', '-i', rawWav, '-ar', '48000', '-ac', '2', wav], { stdio: 'ignore' });
  }
  const dur = probe(wav);
  blocks.push({ ...s, wav, dur });
  console.log(`  • ${s.key.padEnd(8)} ${dur.toFixed(2)}s`);
});

const TOTAL = blocks.reduce((a, b) => a + b.dur + 0.4, 0);  // 0.4s gap per block
console.log(`  → total narration ${TOTAL.toFixed(1)}s`);

// ── 2. Record Playwright walkthrough ─────────────────────────────────
console.log('[2/4] Recording browser…');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    recordVideo: { dir: OUT, size: { width: 1600, height: 900 } },
  });
  const page = await ctx.newPage();
  await page.route('**/*', r => r.continue({ headers: { ...r.request().headers(), 'cache-control': 'no-cache' } }));
  await page.goto('http://127.0.0.1:5000/?cb=' + Date.now(), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  // Enable cinematic camera (orbit + dolly + pitch sweep) for the entire recording.
  await page.evaluate(() => window.__cinema && window.__cinema.on());

  const cum = [];   // cumulative timeline (s)
  let t = 0;
  for (const b of blocks) {
    cum.push(t);
    t += b.dur + 0.4;
  }

  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (typeof b.scene === 'number') {
      await page.locator(`.ssel[data-i="${b.scene}"]`).click();
    }
    // wait for this block's narration duration
    await page.waitForTimeout((b.dur + 0.4) * 1000);
  }

  // tail pad
  await page.waitForTimeout(800);

  // Capture Playwright-managed video path directly (no readdir needed).
  const writtenPath = await page.video().path();
  await page.close();
  await ctx.close();
  // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
  const rawWebm = path.join(OUT, `raw${SUFFIX}.webm`);
  fs.renameSync(writtenPath, rawWebm);
  await browser.close();

  // ── 3. Compose narration audio (sequential WAVs with silences) ─────
  console.log('[3/4] Composing audio…');
  const concatList = path.join(OUT, `concat${SUFFIX}.txt`);
  const silence    = path.join(OUT, 'silence.wav');
  spawnSync('ffmpeg', ['-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', '0.4', silence], { stdio: 'ignore' });
  const lines = [];
  blocks.forEach((b, i) => {
    lines.push(`file '${b.wav}'`);
    if (i < blocks.length - 1) lines.push(`file '${silence}'`);
  });
  fs.writeFileSync(concatList, lines.join('\n') + '\n');
  const narration = path.join(OUT, `narration${SUFFIX}.wav`);
  spawnSync('ffmpeg', ['-y', '-f', 'concat', '-safe', '0', '-i', concatList, '-c', 'copy', narration], { stdio: 'ignore' });

  // ── 4. Mux video + audio ───────────────────────────────────────────
  console.log('[4/4] Muxing final MP4…');
  const out = path.join(OUT, `spacetime_demo${SUFFIX}.mp4`);
  const args = [
    '-y',
    '-i', rawWebm,
    '-i', narration,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k',
    '-shortest',
    '-movflags', '+faststart',
    out
  ];
  spawnSync('ffmpeg', args, { stdio: 'inherit' });
  console.log(`\n✓ done → ${out}`);
})();
