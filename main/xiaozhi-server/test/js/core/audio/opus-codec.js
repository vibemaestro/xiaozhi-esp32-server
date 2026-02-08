import { log } from '../../utils/logger.js';
import { updateScriptStatus } from '../../ui/dom-helper.js'


// Check if Opus library is loaded
export function checkOpusLoaded() {
    try {
        // Check if Module exists (local library exported global variable)
        if (typeof Module === 'undefined') {
            throw new Error('Opus library not loaded, Module object does not exist');
        }

        // Try to use Module.instance (last line exported in libopus.js)
        if (typeof Module.instance !== 'undefined' && typeof Module.instance._opus_decoder_get_size === 'function') {
            // Use Module.instance object to replace global Module object
            window.ModuleInstance = Module.instance;
            log('Opus library loaded successfully (using Module.instance)', 'success');
            updateScriptStatus('Opus library loaded successfully', 'success');

            // Hide status after 3 seconds
            const statusElement = document.getElementById('scriptStatus');
            if (statusElement) statusElement.style.display = 'none';
            return;
        }

        // If Module.instance does not exist, check global Module function
        if (typeof Module._opus_decoder_get_size === 'function') {
            window.ModuleInstance = Module;
            log('Opus library loaded successfully (using global Module)', 'success');
            updateScriptStatus('Opus library loaded successfully', 'success');

            // Hide status after 3 seconds
            const statusElement = document.getElementById('scriptStatus');
            if (statusElement) statusElement.style.display = 'none';
            return;
        }

        throw new Error('Opus decoder function not found, possibly Module structure is incorrect');
    } catch (err) {
        log(`Opus library loading failed, please check if libopus.js file exists and is correct: ${err.message}`, 'error');
        updateScriptStatus('Opus library loading failed, please check if libopus.js file exists and is correct', 'error');
    }
}


// Create an Opus encoder
let opusEncoder = null;
export function initOpusEncoder() {
    try {
        if (opusEncoder) {
            return opusEncoder; // Already initialized
        }

        if (!window.ModuleInstance) {
            log('Cannot create Opus encoder: ModuleInstance is not available', 'error');
            return;
        }

        // Initialize an Opus encoder
        const mod = window.ModuleInstance;
        const sampleRate = 16000; // 16kHz sample rate
        const channels = 1;       // Single channel
        const application = 2048; // OPUS_APPLICATION_VOIP = 2048

        // Create encoder
        opusEncoder = {
            channels: channels,
            sampleRate: sampleRate,
            frameSize: 960, // 60ms @ 16kHz = 60 * 16 = 960 samples
            maxPacketSize: 4000, // Maximum packet size
            module: mod,

            // Initialize encoder
            init: function () {
                try {
                    // Get encoder size
                    const encoderSize = mod._opus_encoder_get_size(this.channels);
                    log(`Opus encoder size: ${encoderSize} bytes`, 'info');

                    // Allocate memory
                    this.encoderPtr = mod._malloc(encoderSize);
                    if (!this.encoderPtr) {
                        throw new Error("Cannot allocate encoder memory");
                    }

                    // Initialize encoder
                    const err = mod._opus_encoder_init(
                        this.encoderPtr,
                        this.sampleRate,
                        this.channels,
                        application
                    );

                    if (err < 0) {
                        throw new Error(`Opus encoder initialization failed: ${err}`);
                    }

                    // Set bitrate (16kbps)
                    mod._opus_encoder_ctl(this.encoderPtr, 4002, 16000); // OPUS_SET_BITRATE

                    // Set complexity (0-10, higher quality but more CPU usage)
                    mod._opus_encoder_ctl(this.encoderPtr, 4010, 5);     // OPUS_SET_COMPLEXITY

                    // Set use DTX (do not transmit silence frames)
                    mod._opus_encoder_ctl(this.encoderPtr, 4016, 1);     // OPUS_SET_DTX

                    log("Opus encoder initialization successful", 'success');
                    return true;
                } catch (error) {
                    if (this.encoderPtr) {
                        mod._free(this.encoderPtr);
                        this.encoderPtr = null;
                    }
                    log(`Opus encoder initialization failed: ${error.message}`, 'error');
                    return false;
                }
            },

            // Encode PCM data to Opus
            encode: function (pcmData) {
                if (!this.encoderPtr) {
                    if (!this.init()) {
                        return null;
                    }
                }

                try {
                    const mod = this.module;

                    // Allocate memory for PCM data
                    const pcmPtr = mod._malloc(pcmData.length * 2); // 2字节/int16

                    // Copy PCM data to HEAP
                    for (let i = 0; i < pcmData.length; i++) {
                        mod.HEAP16[(pcmPtr >> 1) + i] = pcmData[i];
                    }

                    // Allocate memory for output
                    const outPtr = mod._malloc(this.maxPacketSize);

                    // Encode
                    const encodedLen = mod._opus_encode(
                        this.encoderPtr,
                        pcmPtr,
                        this.frameSize,
                        outPtr,
                        this.maxPacketSize
                    );

                    if (encodedLen < 0) {
                        throw new Error(`Opus encoding failed: ${encodedLen}`);
                    }

                    // Copy encoded data
                    const opusData = new Uint8Array(encodedLen);
                    for (let i = 0; i < encodedLen; i++) {
                        opusData[i] = mod.HEAPU8[outPtr + i];
                    }

                    // Free memory
                    mod._free(pcmPtr);
                    mod._free(outPtr);

                    return opusData;
                } catch (error) {
                    log(`Opus encoding error: ${error.message}`, 'error');
                    return null;
                }
            },

            // Destroy encoder
            destroy: function () {
                if (this.encoderPtr) {
                    this.module._free(this.encoderPtr);
                    this.encoderPtr = null;
                }
            }
        };

        opusEncoder.init();
        return opusEncoder;
    } catch (error) {
        log(`Create Opus encoder failed: ${error.message}`, 'error');
        return false;
    }
}