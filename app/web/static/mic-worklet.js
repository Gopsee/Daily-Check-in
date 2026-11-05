// Runs on the audio thread: downsamples the microphone to 16 kHz mono 16-bit PCM
// and posts 100 ms chunks (with a peak level for the on-screen meter).
class MicCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.ratio = sampleRate / (options.processorOptions?.targetRate || 16000);
    this.chunk = new Int16Array(1600);
    this.n = 0;
    this.pos = 0;
    this.sum = 0;
    this.count = 0;
    this.peak = 0;
    this.muted = false;
    this.port.onmessage = (e) => { this.muted = Boolean(e.data.muted); };
  }

  process(inputs) {
    const input = inputs[0][0];
    if (!input) return true;
    for (let i = 0; i < input.length; i++) {
      this.sum += input[i];
      this.count++;
      this.pos++;
      if (this.pos < this.ratio) continue;
      this.pos -= this.ratio;
      // Averaging the samples in each step is a cheap low-pass filter, good enough for speech.
      let v = this.muted ? 0 : this.sum / this.count;
      this.sum = 0;
      this.count = 0;
      v = Math.max(-1, Math.min(1, v));
      this.peak = Math.max(this.peak, Math.abs(v));
      this.chunk[this.n++] = v < 0 ? v * 0x8000 : v * 0x7fff;
      if (this.n === this.chunk.length) {
        this.port.postMessage({ pcm: this.chunk.buffer.slice(0), level: this.peak });
        this.n = 0;
        this.peak = 0;
      }
    }
    return true;
  }
}

registerProcessor("mic-capture", MicCapture);
