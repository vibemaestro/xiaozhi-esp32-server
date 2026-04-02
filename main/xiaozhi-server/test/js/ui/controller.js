// UI controller module
import { loadConfig, saveConfig } from '../config/manager.js';
import { getAudioPlayer } from '../core/audio/player.js';
import { getAudioRecorder } from '../core/audio/recorder.js';
import { getWebSocketHandler } from '../core/network/websocket.js';

// UI controller class
export class UIController {
    constructor() {
        this.isEditing = false;
        this.visualizerCanvas = null;
        this.visualizerContext = null;
        this.audioStatsTimer = null;
    }

    // Initialize
    init() {
        this.visualizerCanvas = document.getElementById('audioVisualizer');
        this.visualizerContext = this.visualizerCanvas.getContext('2d');

        this.initVisualizer();
        this.initEventListeners();
        this.startAudioStatsMonitor();
        loadConfig();
    }

    // Initialize visualizer
    initVisualizer() {
        this.visualizerCanvas.width = this.visualizerCanvas.clientWidth;
        this.visualizerCanvas.height = this.visualizerCanvas.clientHeight;
        this.visualizerContext.fillStyle = '#fafafa';
        this.visualizerContext.fillRect(0, 0, this.visualizerCanvas.width, this.visualizerCanvas.height);
    }

    // Update status display
    updateStatusDisplay(element, text) {
        element.textContent = text;
        element.removeAttribute('style');
        element.classList.remove('connected');
        if (text.includes('Connected')) {
            element.classList.add('connected');
        }
        console.log('Update status:', text, 'Class list:', element.className, 'Style attribute:', element.getAttribute('style'));
    }

    // Update connection status UI
    updateConnectionUI(isConnected) {
        const connectionStatus = document.getElementById('connectionStatus');
        const otaStatus = document.getElementById('otaStatus');
        const connectButton = document.getElementById('connectButton');
        const messageInput = document.getElementById('messageInput');
        const sendTextButton = document.getElementById('sendTextButton');
        const recordButton = document.getElementById('recordButton');

        if (isConnected) {
            this.updateStatusDisplay(connectionStatus, '● WS Connected');
            this.updateStatusDisplay(otaStatus, '● OTA Connected');
            connectButton.textContent = 'Disconnect';
            messageInput.disabled = false;
            sendTextButton.disabled = false;
            recordButton.disabled = false;
        } else {
            this.updateStatusDisplay(connectionStatus, '● WS Not Connected');
            this.updateStatusDisplay(otaStatus, '● OTA Not Connected');
            connectButton.textContent = 'Connect';
            messageInput.disabled = true;
            sendTextButton.disabled = true;
            recordButton.disabled = true;
            // When disconnected, the session status becomes offline
            this.updateSessionStatus(null);
        }
    }

    // Update recording button state
    updateRecordButtonState(isRecording, seconds = 0) {
        const recordButton = document.getElementById('recordButton');
        if (isRecording) {
            recordButton.textContent = `Stop recording ${seconds.toFixed(1)} seconds`;
            recordButton.classList.add('recording');
        } else {
            recordButton.textContent = 'Start recording';
            recordButton.classList.remove('recording');
        }
        recordButton.disabled = false;
    }

    // Update session status UI
    updateSessionStatus(isSpeaking) {
        const sessionStatus = document.getElementById('sessionStatus');
        if (!sessionStatus) return;

        // Keep background elements
        const bgHtml = '<span id="sessionStatusBg" style="position: absolute; left: 0; top: 0; bottom: 0; width: 0%; background: linear-gradient(90deg, rgba(76, 175, 80, 0.2), rgba(33, 150, 243, 0.2)); transition: width 0.15s ease-out, background 0.3s ease; z-index: 0; border-radius: 20px;"></span>';

        if (isSpeaking === null) {
            // Offline status
            sessionStatus.innerHTML = bgHtml + '<span style="position: relative; z-index: 1;"><span class="emoji-large">😶</span> Offline</span>';
            sessionStatus.className = 'status offline';
        } else if (isSpeaking) {
            // Speaking
            sessionStatus.innerHTML = bgHtml + '<span style="position: relative; z-index: 1;"><span class="emoji-large">😶</span> Speaking</span>';
            sessionStatus.className = 'status speaking';
        } else {
            // Listening
            sessionStatus.innerHTML = bgHtml + '<span style="position: relative; z-index: 1;"><span class="emoji-large">😶</span> Listening</span>';
            sessionStatus.className = 'status listening';
        }
    }

    // Update session emotion
    updateSessionEmotion(emoji) {
        const sessionStatus = document.getElementById('sessionStatus');
        if (!sessionStatus) return;

        // Get current text content, extract non-emoji part
        let currentText = sessionStatus.textContent;
        // Remove existing emoji symbols
        currentText = currentText.replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, '').trim();

        // Keep background elements
        const bgHtml = '<span id="sessionStatusBg" style="position: absolute; left: 0; top: 0; bottom: 0; width: 0%; background: linear-gradient(90deg, rgba(76, 175, 80, 0.2), rgba(33, 150, 243, 0.2)); transition: width 0.15s ease-out, background 0.3s ease; z-index: 0; border-radius: 20px;"></span>';

        // Use innerHTML to add styled emoji
        sessionStatus.innerHTML = bgHtml + `<span style="position: relative; z-index: 1;"><span class="emoji-large">${emoji}</span> ${currentText}</span>`;
    }

    // Update audio statistics
    updateAudioStats() {
        const audioPlayer = getAudioPlayer();
        const stats = audioPlayer.getAudioStats();

        const sessionStatus = document.getElementById('sessionStatus');
        const sessionStatusBg = document.getElementById('sessionStatusBg');

        // Only show background progress in speaking state
        if (sessionStatus && sessionStatus.classList.contains('speaking') && sessionStatusBg) {
            if (stats.pendingPlay > 0) {
                // Calculate progress: 5 packets = 50%, 10 packets or more = 100%
                let percentage;
                if (stats.pendingPlay >= 10) {
                    percentage = 100;
                } else {
                    percentage = (stats.pendingPlay / 10) * 100;
                }

                sessionStatusBg.style.width = `${percentage}%`;

                // Change background color based on buffer amount
                if (stats.pendingPlay < 5) {
                    // Buffer不足：橙红色半透明
                    sessionStatusBg.style.background = 'linear-gradient(90deg, rgba(255, 152, 0, 0.25), rgba(255, 87, 34, 0.25))';
                } else if (stats.pendingPlay < 10) {
                    // General: Yellow green semi-transparent
                    sessionStatusBg.style.background = 'linear-gradient(90deg, rgba(205, 220, 57, 0.25), rgba(76, 175, 80, 0.25))';
                } else {
                    // Sufficient: Green blue semi-transparent
                    sessionStatusBg.style.background = 'linear-gradient(90deg, rgba(76, 175, 80, 0.25), rgba(33, 150, 243, 0.25))';
                }
            } else {
                // No buffer, hide background
                sessionStatusBg.style.width = '0%';
            }
        } else {
            // Non-speaking state, hide background
            if (sessionStatusBg) {
                sessionStatusBg.style.width = '0%';
            }
        }
    }

    // Start audio statistics monitoring
    startAudioStatsMonitor() {
        // 每100ms更新一次音频统计
        this.audioStatsTimer = setInterval(() => {
            this.updateAudioStats();
        }, 100);
    }

    // Stop audio statistics monitoring
    stopAudioStatsMonitor() {
        if (this.audioStatsTimer) {
            clearInterval(this.audioStatsTimer);
            this.audioStatsTimer = null;
        }
    }

    // Draw audio visualizer
    drawVisualizer(dataArray) {
        this.visualizerContext.fillStyle = '#fafafa';
        this.visualizerContext.fillRect(0, 0, this.visualizerCanvas.width, this.visualizerCanvas.height);

        const barWidth = (this.visualizerCanvas.width / dataArray.length) * 2.5;
        let barHeight;
        let x = 0;

        for (let i = 0; i < dataArray.length; i++) {
            barHeight = dataArray[i] / 2;

            // Create gradient: from purple to blue to cyan
            const hue = 200 + (barHeight / this.visualizerCanvas.height) * 60; // 200-260 degrees, from cyan to purple
            const saturation = 80 + (barHeight / this.visualizerCanvas.height) * 20; // Saturation 80-100%
            const lightness = 45 + (barHeight / this.visualizerCanvas.height) * 15; // Brightness 45-60%

            this.visualizerContext.fillStyle = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
            this.visualizerContext.fillRect(x, this.visualizerCanvas.height - barHeight, barWidth, barHeight);

            x += barWidth + 1;
        }
    }

    // Initialize event listeners
    initEventListeners() {
        const wsHandler = getWebSocketHandler();
        const audioRecorder = getAudioRecorder();

        // Set WebSocket callbacks
        wsHandler.onConnectionStateChange = (isConnected) => {
            this.updateConnectionUI(isConnected);
        };

        wsHandler.onRecordButtonStateChange = (isRecording) => {
            this.updateRecordButtonState(isRecording);
        };

        wsHandler.onSessionStateChange = (isSpeaking) => {
            this.updateSessionStatus(isSpeaking);
        };

        wsHandler.onSessionEmotionChange = (emoji) => {
            this.updateSessionEmotion(emoji);
        };

        // Set audio recorder callbacks
        audioRecorder.onRecordingStart = (seconds) => {
            this.updateRecordButtonState(true, seconds);
        };

        audioRecorder.onRecordingStop = () => {
            this.updateRecordButtonState(false);
        };

        audioRecorder.onVisualizerUpdate = (dataArray) => {
            this.drawVisualizer(dataArray);
        };

        // Connect button
        const connectButton = document.getElementById('connectButton');
        let isConnecting = false;

        const handleConnect = async () => {
            if (isConnecting) return;

            if (wsHandler.isConnected()) {
                wsHandler.disconnect();
            } else {
                isConnecting = true;
                await wsHandler.connect();
                isConnecting = false;
            }
        };

        connectButton.addEventListener('click', handleConnect);

        // Device configuration panel edit/confirm switch
        const toggleButton = document.getElementById('toggleConfig');
        const deviceMacInput = document.getElementById('deviceMac');
        const deviceNameInput = document.getElementById('deviceName');
        const clientIdInput = document.getElementById('clientId');

        toggleButton.addEventListener('click', () => {
            this.isEditing = !this.isEditing;

            deviceMacInput.disabled = !this.isEditing;
            deviceNameInput.disabled = !this.isEditing;
            clientIdInput.disabled = !this.isEditing;

            toggleButton.textContent = this.isEditing ? 'Confirm' : 'Edit';

            if (!this.isEditing) {
                saveConfig();
            }
        });

        // Tab switch
        const tabs = document.querySelectorAll('.tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                tab.classList.add('active');
                const tabContent = document.getElementById(`${tab.dataset.tab}Tab`);
                tabContent.classList.add('active');

                if (tab.dataset.tab === 'voice') {
                    setTimeout(() => {
                        this.initVisualizer();
                    }, 50);
                }
            });
        });

        // Send text message
        const messageInput = document.getElementById('messageInput');
        const sendTextButton = document.getElementById('sendTextButton');

        const sendMessage = () => {
            const message = messageInput.value.trim();
            if (message && wsHandler.sendTextMessage(message)) {
                messageInput.value = '';
            }
        };

        sendTextButton.addEventListener('click', sendMessage);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        // Record button
        const recordButton = document.getElementById('recordButton');
        recordButton.addEventListener('click', () => {
            if (audioRecorder.isRecording) {
                audioRecorder.stop();
            } else {
                audioRecorder.start();
            }
        });

        // Window size change
        window.addEventListener('resize', () => this.initVisualizer());
    }
}

// Create singleton
let uiControllerInstance = null;

export function getUIController() {
    if (!uiControllerInstance) {
        uiControllerInstance = new UIController();
    }
    return uiControllerInstance;
}
