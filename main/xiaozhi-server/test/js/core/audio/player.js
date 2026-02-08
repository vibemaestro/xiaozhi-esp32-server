// Audio player module
import { log } from '../../utils/logger.js';
import BlockingQueue from '../../utils/blocking-queue.js';
import { createStreamingContext } from './stream-context.js';

// Audio player class
export class AudioPlayer {
    constructor() {
        // Audio parameters
        this.SAMPLE_RATE = 16000;
        this.CHANNELS = 1;
        this.FRAME_SIZE = 960;
        this.MIN_AUDIO_DURATION = 0.12;

        // States
        this.audioContext = null;
        this.opusDecoder = null;
        this.streamingContext = null;
        this.queue = new BlockingQueue();
        this.isPlaying = false;
    }

    // Get or create AudioContext
    getAudioContext() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.SAMPLE_RATE,
                latencyHint: 'interactive'
            });
            log('Create audio context, sample rate: ' + this.SAMPLE_RATE + 'Hz', 'debug');
        }
        return this.audioContext;
    }

    // Initialize Opus decoder
    async initOpusDecoder() {
        if (this.opusDecoder) return this.opusDecoder;

        try {
            if (typeof window.ModuleInstance === 'undefined') {
                if (typeof Module !== 'undefined') {
                    window.ModuleInstance = Module;
                    log('Use global Module as ModuleInstance', 'info');
                } else {
                    throw new Error('Opus library not loaded, ModuleInstance and Module object do not exist');
                }
            }

            const mod = window.ModuleInstance;

            this.opusDecoder = {
                channels: this.CHANNELS,
                rate: this.SAMPLE_RATE,
                frameSize: this.FRAME_SIZE,
                module: mod,
                decoderPtr: null,

                init: function () {
                    if (this.decoderPtr) return true;

                    const decoderSize = mod._opus_decoder_get_size(this.channels);
                    log(`Opus decoder size: ${decoderSize} bytes`, 'debug');

                    this.decoderPtr = mod._malloc(decoderSize);
                    if (!this.decoderPtr) {
                        throw new Error("Cannot allocate decoder memory");
                    }

                    const err = mod._opus_decoder_init(
                        this.decoderPtr,
                        this.rate,
                        this.channels
                    );

                    if (err < 0) {
                        this.destroy();
                        throw new Error(`Opus decoder initialization failed: ${err}`);
                    }

                    log("Opus decoder initialization successful", 'success');
                    return true;
                },

                decode: function (opusData) {
                    if (!this.decoderPtr) {
                        if (!this.init()) {
                            throw new Error("Decoder not initialized and cannot be initialized");
                        }
                    }

                    try {
                        const mod = this.module;

                        const opusPtr = mod._malloc(opusData.length);
                        mod.HEAPU8.set(opusData, opusPtr);

                        const pcmPtr = mod._malloc(this.frameSize * 2);

                        const decodedSamples = mod._opus_decode(
                            this.decoderPtr,
                            opusPtr,
                            opusData.length,
                            pcmPtr,
                            this.frameSize,
                            0
                        );

                        if (decodedSamples < 0) {
                            mod._free(opusPtr);
                            mod._free(pcmPtr);
                            throw new Error(`Opus decoding failed: ${decodedSamples}`);
                        }

                        const decodedData = new Int16Array(decodedSamples);
                        for (let i = 0; i < decodedSamples; i++) {
                            decodedData[i] = mod.HEAP16[(pcmPtr >> 1) + i];
                        }

                        mod._free(opusPtr);
                        mod._free(pcmPtr);

                        return decodedData;
                    } catch (error) {
                        log(`Opus decoding error: ${error.message}`, 'error');
                        return new Int16Array(0);
                    }
                },

                destroy: function () {
                    if (this.decoderPtr) {
                        this.module._free(this.decoderPtr);
                        this.decoderPtr = null;
                    }
                }
            };

            if (!this.opusDecoder.init()) {
                throw new Error("Opus decoder initialization failed");
            }

            return this.opusDecoder;

        } catch (error) {
            log(`Opus decoder initialization failed: ${error.message}`, 'error');
            this.opusDecoder = null;
            throw error;
        }
    }

    // Start audio buffering
    async startAudioBuffering() {
        log("Start audio buffering...", 'info');

        this.initOpusDecoder().catch(error => {
            log(`Pre-initialize Opus decoder failed: ${error.message}`, 'warning');
        });

        const timeout = 400;
        while (true) {
            const packets = await this.queue.dequeue(
                6,
                timeout,
                (count) => {
                    log(`Buffer timeout, current buffer packet count: ${count}, start playing`, 'info');
                }
            );
            if (packets.length) {
                log(`Buffered ${packets.length} audio packets, start playing`, 'info');
                this.streamingContext.pushAudioBuffer(packets);
            }

            while (true) {
                const data = await this.queue.dequeue(99, 30);
                if (data.length) {
                    this.streamingContext.pushAudioBuffer(data);
                } else {
                    break;
                }
            }
        }
    }

    // Play buffered audio
    async playBufferedAudio() {
        try {
            this.audioContext = this.getAudioContext();

            if (!this.opusDecoder) {
                log('Initialize Opus decoder...', 'info');
                try {
                    this.opusDecoder = await this.initOpusDecoder();
                    if (!this.opusDecoder) {
                        throw new Error('Decoder initialization failed');
                    }
                    log('Opus decoder initialization successful', 'success');
                } catch (error) {
                    log('Opus decoder initialization failed: ' + error.message, 'error');
                    this.isPlaying = false;
                    return;
                }
            }

            if (!this.streamingContext) {
                this.streamingContext = createStreamingContext(
                    this.opusDecoder,
                    this.audioContext,
                    this.SAMPLE_RATE,
                    this.CHANNELS,
                    this.MIN_AUDIO_DURATION
                );
            }

            this.streamingContext.decodeOpusFrames();
            this.streamingContext.startPlaying();

        } catch (error) {
            log(`Play buffered audio error: ${error.message}`, 'error');
            this.isPlaying = false;
            this.streamingContext = null;
        }
    }

    // Add audio data to queue
    enqueueAudioData(opusData) {
        if (opusData.length > 0) {
            this.queue.enqueue(opusData);
        } else {
            log('Received empty audio data frame,可能是结束标志', 'warning');
            if (this.isPlaying && this.streamingContext) {
                this.streamingContext.endOfStream = true;
            }
        }
    }

    // Preload decoder
    async preload() {
        log('Preload Opus decoder...', 'info');
        try {
            await this.initOpusDecoder();
            log('Opus decoder preload successful', 'success');
        } catch (error) {
            log(`Opus decoder preload failed: ${error.message}, will retry when needed`, 'warning');
        }
    }

    // Start playback system
    async start() {
        await this.preload();
        this.playBufferedAudio();
        this.startAudioBuffering();
    }

    // Get audio packet statistics
    getAudioStats() {
        if (!this.streamingContext) {
            return {
                pendingDecode: 0,
                pendingPlay: 0,
                totalPending: 0
            };
        }

        const pendingDecode = this.streamingContext.getPendingDecodeCount();
        const pendingPlay = this.streamingContext.getPendingPlayCount();

        return {
            pendingDecode,  // Pending decode packet count
            pendingPlay,    // Pending play packet count
            totalPending: pendingDecode + pendingPlay  // 总待处理包数
        };
    }

    // Clear all audio buffers and stop playing
    clearAllAudio() {
        log('AudioPlayer: clear all audio', 'info');

        // Clear receive queue (using clear method to keep object reference)
        this.queue.clear();

        // Clear all buffers in streaming context
        if (this.streamingContext) {
            this.streamingContext.clearAllBuffers();
        }

        log('AudioPlayer: audio cleared', 'success');
    }
}

// Create singleton
let audioPlayerInstance = null;

export function getAudioPlayer() {
    if (!audioPlayerInstance) {
        audioPlayerInstance = new AudioPlayer();
    }
    return audioPlayerInstance;
}
