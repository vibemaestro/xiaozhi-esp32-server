// 主应用入口
import { log } from './utils/logger.js';
import { checkOpusLoaded, initOpusEncoder } from './core/audio/opus-codec.js';
import { getUIController } from './ui/controller.js';
import { getAudioPlayer } from './core/audio/player.js';
import { initMcpTools } from './core/mcp/tools.js';

// 应用类
class App {
    constructor() {
        this.uiController = null;
        this.audioPlayer = null;
    }

    // 初始化应用
    async init() {
        log('Initializing application...', 'info');

        // Initialize UI controller
        this.uiController = getUIController();
        this.uiController.init();

        // Check Opus library
        checkOpusLoaded();

        // Initialize Opus encoder
        initOpusEncoder();

        // Initialize audio player
        this.audioPlayer = getAudioPlayer();
        await this.audioPlayer.start();

        // Initialize MCP tools
        initMcpTools();

        log('Application initialized successfully', 'success');
    }
}

// Create and start application
const app = new App();

// Initialize after DOM loading
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => app.init());
} else {
    app.init();
}

export default app;
