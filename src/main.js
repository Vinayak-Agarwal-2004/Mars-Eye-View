import 'leaflet/dist/leaflet.css';
import { MapManager } from './managers/MapManager.js';
import { DataManager } from './managers/DataManager.js';
import { UIManager } from './managers/UIManager.js';
import { InteractionManager } from './managers/InteractionManager.js';
import { SufferingLayer } from './managers/SufferingLayer.js';

(async () => {
    try {
        console.log("🚀 Initializing Application...");

        // 1. Initialize UI Manager (Panels, Tabs)
        const uiManager = new UIManager();
        uiManager.showLoader('Startup: initializing data sources...', 0.05);

        // 2. Initialize Data Manager (Sources, Config)
        const dataManager = new DataManager();
        await dataManager.init();
        await dataManager.startup((msg, progress) => uiManager.showLoader(`Startup: ${msg}`, progress));

        // Start the Live Stream (Events)
        dataManager.startStream();

        // 3. Initialize Map Manager (Leaflet)
        const mapManager = new MapManager('map', dataManager, uiManager);
        await mapManager.init();

        // 4. Initialize Interaction Manager (Disputes, etc.)
        const interactionManager = new InteractionManager(mapManager.map, dataManager, uiManager);
        await interactionManager.init();

        // 5. Initialize Suffering Tracker
        const sufferingLayer = new SufferingLayer(mapManager.map, dataManager, uiManager, interactionManager);
        await sufferingLayer.init();

        // Global Access for Debugging
        window.app = { mapManager, dataManager, uiManager, interactionManager, sufferingLayer };

        console.log("✅ Application Ready");
    } catch (err) {
        console.error("CRITICAL INIT FAILURE:", err);
        // Force remove loader
        const loader = document.getElementById('loader');
        if (loader) loader.style.display = 'none';

        // Show Error Modal
        const errDiv = document.createElement('div');
        errDiv.style.position = 'fixed';
        errDiv.style.top = '0';
        errDiv.style.left = '0';
        errDiv.style.width = '100vw';
        errDiv.style.height = '100vh';
        errDiv.style.background = 'rgba(0,0,0,0.9)';
        errDiv.style.color = '#ff6b6b';
        errDiv.style.display = 'flex';
        errDiv.style.flexDirection = 'column';
        errDiv.style.alignItems = 'center';
        errDiv.style.justifyContent = 'center';
        errDiv.style.zIndex = '9999';
        errDiv.innerHTML = `<h1>System Startup Failed</h1><p>${err.message}</p><pre>${err.stack}</pre>`;
        document.body.appendChild(errDiv);
    }
})();
