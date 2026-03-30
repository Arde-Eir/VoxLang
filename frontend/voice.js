/**
 * Utter – Voice Capture Module
 * =============================
 * Handles microphone access, audio recording, noise filtering,
 * silence detection, and sending audio to the backend STT pipeline.
 *
 * Usage:
 *   const voice = new VoiceCapture({ onCode, onTranscript, onVolume, onError, onStateChange });
 *   await voice.start();
 *   voice.stop();      // stop recording, process audio
 *   voice.stopAll();   // stop + release mic + close audio context
 *   voice.getVolume(); // 0.0 – 1.0 normalised RMS (call from rAF loop)
 */

export class VoiceCapture {
  // ── Silence detection defaults ───────────────────────────────────────────
  static SILENCE_THRESHOLD = 0.012; // RMS below this is considered silence
  static SILENCE_DURATION  = 1400;  // ms of silence before auto-stop
  static MIN_SPEECH_MS     = 300;   // discard blobs shorter than this
  static MAX_RECORDING_MS  = 30_000; // hard cap – prevents runaway recordings

  constructor(opts = {}) {
    this.onCode        = opts.onCode        || (() => {});
    this.onTranscript  = opts.onTranscript  || (() => {});
    this.onVolume      = opts.onVolume      || (() => {});  // cb(rms: 0–1)
    this.onError       = opts.onError       || (() => {});
    this.onStateChange = opts.onStateChange || (() => {});
    this.getContext    = opts.getContext     || (() => '');
    const defaultBase = window.location.origin; // Dynamically gets your Vercel URL
this.apiBase = (opts.apiBase || defaultBase).replace(/\/$/, '');

    this._recorder     = null;
    this._stream       = null;
    this._audioCtx     = null;
    this._analyser     = null;
    this._chunks       = [];
    this._isRecording  = false;
    this._silenceTimer = null;
    this._maxTimer     = null;
    this._rafId        = null;
    this._speechStart  = 0;
  }

  // ── Public getters ────────────────────────────────────────────────────────
  get isRecording() { return this._isRecording; }

  /** Live RMS volume 0–1. Call from your own rAF loop for a VU meter. */
  getVolume() {
    if (!this._analyser) return 0;
    const buf = new Uint8Array(this._analyser.fftSize);
    this._analyser.getByteTimeDomainData(buf);
    const rms = Math.sqrt(
      buf.reduce((s, v) => s + ((v - 128) / 128) ** 2, 0) / buf.length
    );
    return Math.min(1, rms / VoiceCapture.SILENCE_THRESHOLD);
  }

  // ── Permission ────────────────────────────────────────────────────────────
  async requestPermission() {
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:  true,
          sampleRate:       16_000,
        },
      });
      return true;
    } catch (err) {
      this._emitError('Microphone access denied: ' + err.message);
      return false;
    }
  }

  // ── Start recording ───────────────────────────────────────────────────────
  async start() {
    if (this._isRecording) return;

    if (!this._stream) {
      const ok = await this.requestPermission();
      if (!ok) return;
    }

    // Build audio graph: source → highpass → peaking shelf → analyser + recorder dest
    this._audioCtx = new AudioContext({ sampleRate: 16_000 });
    const source   = this._audioCtx.createMediaStreamSource(this._stream);

    // High-pass: cut rumble / AC hum below 80 Hz
    const hpFilter = this._audioCtx.createBiquadFilter();
    hpFilter.type            = 'highpass';
    hpFilter.frequency.value = 80;
    hpFilter.Q.value         = 0.7;

    // Peaking EQ: lightly boost speech presence band (around 2 kHz)
    const shelf = this._audioCtx.createBiquadFilter();
    shelf.type            = 'peaking';
    shelf.frequency.value = 2000;
    shelf.gain.value      = 3;
    shelf.Q.value         = 0.5;

    this._analyser                       = this._audioCtx.createAnalyser();
    this._analyser.fftSize               = 512;
    this._analyser.smoothingTimeConstant = 0.6;

    const dest = this._audioCtx.createMediaStreamDestination();

    source.connect(hpFilter);
    hpFilter.connect(shelf);
    shelf.connect(this._analyser);
    shelf.connect(dest);

    const mimeType    = this._bestMime();
    this._recorder    = new MediaRecorder(dest.stream, { mimeType });
    this._chunks      = [];
    this._speechStart = Date.now();

    this._recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) this._chunks.push(e.data);
    };
    this._recorder.onstop = () => this._process(mimeType);
    this._recorder.start(100); // 100 ms timeslice for low latency

    this._isRecording = true;
    this.onStateChange('recording');

    this._startSilenceLoop();

    // Hard cap: auto-stop after MAX_RECORDING_MS regardless of speech
    this._maxTimer = setTimeout(() => {
      if (this._isRecording) this.stop();
    }, VoiceCapture.MAX_RECORDING_MS);
  }

  // ── Stop recording ────────────────────────────────────────────────────────
  stop() {
    if (!this._isRecording) return;

    clearTimeout(this._silenceTimer);
    clearTimeout(this._maxTimer);
    cancelAnimationFrame(this._rafId);
    this._silenceTimer = null;
    this._maxTimer     = null;
    this._rafId        = null;

    if (this._recorder && this._recorder.state !== 'inactive') {
      this._recorder.stop();
    }

    this._isRecording = false;
    this.onStateChange('processing');
  }

  /** Stop recording AND fully release the microphone and audio context. */
  stopAll() {
    this.stop();
    this._releaseHardware();
    this.onStateChange('idle');
  }

  // ── Silence detection loop ────────────────────────────────────────────────
  _startSilenceLoop() {
    const tick = () => {
      if (!this._isRecording || !this._analyser) return;

      const buf = new Uint8Array(this._analyser.fftSize);
      this._analyser.getByteTimeDomainData(buf);
      const rms = Math.sqrt(
        buf.reduce((s, v) => s + ((v - 128) / 128) ** 2, 0) / buf.length
      );

      // Emit normalised volume (0–1) for external VU meters
      this.onVolume(Math.min(1, rms / VoiceCapture.SILENCE_THRESHOLD));

      if (rms < VoiceCapture.SILENCE_THRESHOLD) {
        if (!this._silenceTimer) {
          this._silenceTimer = setTimeout(() => {
            this._silenceTimer = null;
            if (this._isRecording && this._chunks.length > 0) this.stop();
          }, VoiceCapture.SILENCE_DURATION);
        }
      } else {
        clearTimeout(this._silenceTimer);
        this._silenceTimer = null;
      }

      this._rafId = requestAnimationFrame(tick);
    };

    this._rafId = requestAnimationFrame(tick);
  }

  // ── Audio processing pipeline ─────────────────────────────────────────────
  async _process(mimeType) {
    if (!this._chunks.length) {
      this.onStateChange('idle');
      return;
    }

    // Discard clips that are too short to contain real speech
    const duration = Date.now() - this._speechStart;
    if (duration < VoiceCapture.MIN_SPEECH_MS) {
      this._chunks = [];
      this.onStateChange('idle');
      return;
    }

    const blob   = new Blob(this._chunks, { type: mimeType });
    this._chunks = [];
    const b64    = await this._blobToBase64(blob);

    try {
      // ── Step 1: Speech-to-text ─────────────────────────────────────────
      const sttRes = await this._post('/transcribe', {
        audio_b64: b64,
        mime_type: mimeType,
      });

      if (!sttRes.transcript?.trim()) {
        this.onStateChange('idle');
        return;
      }

      this.onTranscript({
        text:          sttRes.transcript,
        confidence:    sttRes.confidence    ?? 1,
        lowConfidence: sttRes.low_confidence ?? false,
      });

      // ── Step 1b: Optional transcript correction for low-confidence STT ──
      let transcript = sttRes.transcript;
      if (sttRes.low_confidence) {
        try {
          const corrRes = await this._post('/correct', { transcript });
          if (corrRes.corrected?.trim()) transcript = corrRes.corrected;
        } catch { /* silently fall back to raw transcript */ }
      }

      if (!transcript.trim()) {
        this.onStateChange('idle');
        return;
      }

      // ── Step 2: Code generation ────────────────────────────────────────
      this.onStateChange('generating');
      const genRes = await this._post('/generate', {
        transcript,
        context: this.getContext(),
      });

      this.onCode(genRes.code?.trim() || '');

    } catch (err) {
      this._emitError('Voice pipeline error: ' + err.message);
    } finally {
      this.onStateChange('idle');
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  /** POST JSON, return parsed response. Throws on non-2xx. */
  async _post(path, body) {
    const res = await fetch(this.apiBase + path, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${path} returned HTTP ${res.status}`);
    return res.json();
  }

  /**
   * Convert a Blob to a base64 string.
   * Uses chunked String.fromCharCode to avoid call-stack overflow
   * on large audio buffers (> ~50 kB).
   */
  async _blobToBase64(blob) {
    const arrayBuf = await blob.arrayBuffer();
    const bytes    = new Uint8Array(arrayBuf);
    let   binary   = '';
    const CHUNK    = 8192;
    for (let i = 0; i < bytes.length; i += CHUNK) {
      binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
    }
    return btoa(binary);
  }

  /** Return the best MediaRecorder MIME type supported by this browser. */
  _bestMime() {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ];
    return candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? 'audio/webm';
  }

  /** Release mic tracks and close the AudioContext. */
  _releaseHardware() {
    this._stream?.getTracks().forEach(t => t.stop());
    this._stream   = null;
    this._audioCtx?.close();
    this._audioCtx = null;
    this._analyser = null;
  }

  /** Log and forward an error. */
  _emitError(msg) {
    console.error('[VoiceCapture]', msg);
    this.onError(msg);
  }
}