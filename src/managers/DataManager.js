import { API_BASE } from '../config.js';

function toGeoJSONApiUrl(path) {
    if (path === 'data/countries.geojson') return `${API_BASE}/api/geojson/world`;
    const m1 = path && path.match(/^data\/adm1\/([A-Z]{3})\.geojson$/i);
    if (m1) return `${API_BASE}/api/geojson/adm1/${m1[1].toUpperCase()}`;
    const m2 = path && path.match(/^data\/adm2\/([A-Z]{3})\.geojson$/i);
    if (m2) return `${API_BASE}/api/geojson/adm2/${m2[1].toUpperCase()}`;
    return null;
}

export class DataManager {
    constructor() {
        this.cache = {};
        this.countrySources = {};
        this.geoData = null;
        this.isPaused = false;
        this.lastHash = "";
        this.countryInfo = {};
        this.volatileData = {};
        this.currencyRates = {};
        this.capitalData = {};
    }


    async startStream() {
        await this.fetchData();
        // Poll API every 15s (faster than 60s because local API is fast)
        setInterval(() => this.fetchData(), 15000);
    }

    async startup(onStatus) {
        const report = (msg, progress) => {
            if (typeof onStatus === 'function') onStatus(msg, progress);
            else console.log(`[Startup] ${msg}`);
        };

        report('Checking backend health...', 0.1);
        const healthy = await this.waitForBackend();
        if (!healthy) {
            report('Backend not reachable. Continuing with cached data.', 0.2);
            return;
        }

        report('Loading live firehose data...', 0.3);
        await this.waitForLiveData();

        report('Startup complete.', 0.85);
    }


    async waitForBackend(retries = 12, delayMs = 1000) {
        for (let i = 0; i < retries; i++) {
            const health = await this.fetchJSON(`${API_BASE}/api/health`);

            if (health && health.status === 'ok') return true;
            await this.sleep(delayMs);
        }

        return false;
    }

    async waitForLiveData(retries = 12, delayMs = 1500) {
        for (let i = 0; i < retries; i++) {
            const data = await this.fetchJSON(`${API_BASE}/api/live`);

            if (data && Array.isArray(data.features) && data.features.length > 0) {
                this.geoData = data;
                return true;
            }
            await this.sleep(delayMs);
        }
        return false;
    }

    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async fetchData() {
        // Call our new Fast backend
        const data = await this.fetchJSON(`${API_BASE}/api/live`);
        if (data) {
            // Hash check to avoid redraws? For now just raw updates
            this.geoData = data;
        }
    }

    // Called by UIManager when a country is clicked
    async getCastForecast(countryName, admin1) {
        if (!countryName) return null;
        const q = new URLSearchParams({ country: countryName });
        if (admin1) q.append("admin1", admin1);

        return await this.fetchJSON(`${API_BASE}/api/cast?${q.toString()}`);
    }

    async init() {
        const [sources, info, volatile, currency, capitals] = await Promise.all([
            this.fetchJSON('data/country_sources.json'),
            this.fetchJSON('data/country_info.json'),
            this.fetchJSON('data/volatile_data.json'),
            this.fetchJSON('data/currency_rates.json'),
            this.fetchJSON('data/capitals.json')
        ]);

        this.countrySources = sources || {};
        this.countryInfo = info || {};
        this.volatileData = volatile || {};
        this.currencyRates = currency || {};
        this.capitalData = capitals || {};
    }

    async fetchJSON(url, cacheKey) {
        if (cacheKey && this.cache[cacheKey]) return this.cache[cacheKey];
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (cacheKey) this.cache[cacheKey] = data;
            return data;
        } catch (e) {
            console.error(`[DataManager] Failed: ${url}`, e);
            return null;
        }
    }

    async fetchGeoJSON(path, cacheKey) {
        const apiUrl = toGeoJSONApiUrl(path);
        return apiUrl ? this.fetchJSON(apiUrl, cacheKey) : this.fetchJSON(path, cacheKey);
    }

    getCountryInfo(iso) {
        return this.countryInfo[iso] || null;
    }

    getVolatileData(iso) {
        return (this.volatileData.countries || {})[iso] || null;
    }

    getCapitalData() {
        return this.capitalData;
    }
}
