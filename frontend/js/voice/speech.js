/**
 * Alab-Mart Speech Handler
 * Manages Audio Recording, WAV Encoding, and TTS Playback
 */

class SpeechHandler {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.audioContext = null;
    this.stream = null;
    this.isRecording = false;
    this.currentAudio = null;
    this.silenceTimer = null;
    this.analyser = null;
  }

  /**
   * Request microphone permission and initialize audio stream
   */
  async initStream() {
    if (!this.stream) {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
  }

  /**
   * Start recording voice input from user with VAD (Voice Activity Detection)
   * @param {Function} onSilenceCallback Automatically stop when user finishes speaking
   */
  async startRecording(onSilenceCallback = null) {
    await this.initStream();
    this.audioChunks = [];
    this.isRecording = true;

    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioContext.createMediaStreamSource(this.stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 512;
    source.connect(this.analyser);

    this.mediaRecorder = new MediaRecorder(this.stream);
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.start(100);

    if (onSilenceCallback) {
      this.detectSilence(onSilenceCallback);
    }
  }

  /**
   * Silence detector to auto-stop recording after user stops talking
   */
  detectSilence(onSilenceCallback) {
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    let silenceStart = Date.now();
    const SILENCE_THRESHOLD = 15; // Threshold value for speech vs silence
    const SILENCE_DURATION = 1500; // Stop after 1.5s of continuous silence

    const checkAudio = () => {
      if (!this.isRecording) return;

      this.analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      let average = sum / bufferLength;

      if (average < SILENCE_THRESHOLD) {
        if (Date.now() - silenceStart > SILENCE_DURATION) {
          if (this.isRecording) {
            onSilenceCallback();
          }
          return;
        }
      } else {
        silenceStart = Date.now();
      }

      requestAnimationFrame(checkAudio);
    };

    requestAnimationFrame(checkAudio);
  }

  /**
   * Stop recording audio and return audio blob
   * @returns {Promise<Blob>}
   */
  stopRecording() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || !this.isRecording) {
        resolve(null);
        return;
      }

      this.isRecording = false;
      this.mediaRecorder.onstop = async () => {
        const rawBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        const wavBlob = await this.convertToWav(rawBlob);
        if (this.audioContext) {
          this.audioContext.close();
        }
        resolve(wavBlob);
      };

      this.mediaRecorder.stop();
    });
  }

  /**
   * Convert WebM audio blob to 16kHz PCM WAV for Whisper.cpp compatibility
   */
  async convertToWav(blob) {
    const arrayBuffer = await blob.arrayBuffer();
    const tempAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuffer = await tempAudioContext.decodeAudioData(arrayBuffer);
    
    // Resample to 16000 Hz Mono
    const offlineCtx = new OfflineAudioContext(1, audioBuffer.duration * 16000, 16000);
    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineCtx.destination);
    source.start();

    const renderedBuffer = await offlineCtx.startRendering();
    tempAudioContext.close();

    return this.encodeWAV(renderedBuffer.getChannelData(0), 16000);
  }

  /**
   * Encode raw float PCM into 16-bit WAV file format
   */
  encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    /* RIFF identifier */
    this.writeString(view, 0, 'RIFF');
    /* RIFF chunk length */
    view.setUint32(4, 36 + samples.length * 2, true);
    /* RIFF type */
    this.writeString(view, 8, 'WAVE');
    /* format chunk identifier */
    this.writeString(view, 12, 'fmt ');
    /* format chunk length */
    view.setUint32(16, 16, true);
    /* sample format (raw PCM) */
    view.setUint16(20, 1, true);
    /* channel count (mono) */
    view.setUint16(22, 1, true);
    /* sample rate */
    view.setUint32(24, sampleRate, true);
    /* byte rate (sampleRate * 2) */
    view.setUint32(28, sampleRate * 2, true);
    /* block align */
    view.setUint16(32, 2, true);
    /* bits per sample */
    view.setUint16(34, 16, true);
    /* data chunk identifier */
    this.writeString(view, 36, 'data');
    /* data chunk length */
    view.setUint32(40, samples.length * 2, true);

    // Float to 16-bit PCM conversion
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: 'audio/wav' });
  }

  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  /**
   * Play TTS Response Audio
   * @param {Blob|string} audioData Audio Blob or Audio URL
   * @returns {Promise<void>} Resolves when audio finishes playing
   */
  playAudio(audioData) {
    return new Promise((resolve, reject) => {
      if (this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
      }

      const src = typeof audioData === 'string' ? audioData : URL.createObjectURL(audioData);
      this.currentAudio = new Audio(src);

      this.currentAudio.onended = () => {
        resolve();
      };

      this.currentAudio.onerror = (err) => {
        console.error("Audio playback error:", err);
        reject(err);
      };

      this.currentAudio.play().catch(reject);
    });
  }

  /**
   * Stop speech or active playback
   */
  stopAudio() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
  }
}

window.speechHandler = new SpeechHandler();