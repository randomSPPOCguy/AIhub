/**
 * Simple 1-req/sec queue for MusicBrainz.
 * Call mbQueue.enqueue(() => doFetch());
 */
export class RateQueue {
  constructor(intervalMs = 1000) {
    this.intervalMs = intervalMs;
    this.queue = [];
    this.running = false;
  }
  enqueue(fn) {
    return new Promise((resolve, reject) => {
      this.queue.push({ fn, resolve, reject });
      this.run();
    });
  }
  async run() {
    if (this.running) return;
    this.running = true;
    while (this.queue.length) {
      const { fn, resolve, reject } = this.queue.shift();
      try {
        const out = await fn();
        resolve(out);
      } catch (e) {
        reject(e);
      }
      await new Promise(r => setTimeout(r, this.intervalMs));
    }
    this.running = false;
  }
}
