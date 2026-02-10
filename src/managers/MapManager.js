import L from 'leaflet';

export class MapManager {
    constructor(mapId, dataManager, uiManager) {
        this.mapId = mapId;
        this.data = dataManager;
        this.ui = uiManager;
        this.map = null;
        this.currentLayer = null;
        this.neighborsLayer = null;
        this.navStack = [{ name: 'World', iso: '', level: 0 }];
        this.isNavigating = false;
        this.currentLevel = 0;
        this.currentParentISO = '';
        this.currentStyleContext = null;

        this.castVisible = false;
        this.castData = null;

        this.admin1Lookup = null;
        this.adminAliasMap = new Map();
        this.castScale = null;

        this.ZOOM_THRESHOLDS = {
            1: 4,   // Below this zoom, go from state to world
            2: 6    // Below this zoom, go from district to state
        };

        window.addEventListener('cast-tab-visibility', (e) => {
            this.castVisible = !!e.detail?.visible;
            if (!this.castVisible) {
                this.clearCastChoropleth();
            } else {
                this.applyCastChoropleth();
            }
        });

        window.addEventListener('cast-data-update', (e) => {
            this.castData = e.detail || null;
            if (this.castVisible) {
                this.applyCastChoropleth();
            }
        });

        window.addEventListener('map-level-change', (e) => {
            const level = e.detail?.level;
            if (level !== 1) {
                this.clearCastChoropleth();
            } else if (this.castVisible) {
                this.applyCastChoropleth();
            }
        });
    }

    async init() {
        this.initMap();
        this.ui.showLoader('Loading world...', 0.9);

        // Load initial world data
        const worldData = await this.data.fetchJSON('data/countries.geojson', 'world');
        if (!worldData) {
            this.ui.hideLoader();
            this.ui.toast('Failed to load map');
            return;
        }

        this.ui.showLoader('Finalizing map...', 1.0);
        this.ui.hideLoader();
        this.renderLayer(worldData, 0);
        this.renderBreadcrumb();

        // Wire up UI close button
        this.ui.$('panel-close').onclick = () => this.ui.hidePanel();
    }

    initMap() {
        this.map = L.map(this.mapId, { center: [20, 0], zoom: 2, minZoom: 1.5, maxZoom: 18 });
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
            attribution: '© OSM © CARTO', subdomains: 'abcd'
        }).addTo(this.map);

        this.map.on('zoomend', () => this.handleZoomEnd());
    }

    handleZoomEnd() {
        if (this.isNavigating) return;
        // Auto-navigation logic (currently disabled/commented out in original app.js logic, keeping it consistent)
    }

    // --- Styling & Utils ---

    getHashColor(str) {
        if (!str) return '#3388ff';
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        const h = Math.abs(hash % 360);
        const s = 65 + (Math.abs(hash) % 20);
        const l = 45 + (Math.abs(hash >> 8) % 15);
        return `hsl(${h}, ${s}%, ${l}%)`;
    }

    getName(props) {
        return props.shapeName || props.ADMIN || props.NAME || props.name ||
            props.reg_name || props.state_name || props.province_name ||
            props.LABEL || props.Label || 'Unknown';
    }

    getISO(props, fallback) {
        let iso = props.shapeGroup || props.ADM0_A3 || props.ISO_A3 || props['ISO3166-1-Alpha-3'] ||
            props.reg_istat_code || props.code_hasc || props.HASC_1 || fallback || '';
        if (iso === '-99') iso = props.ADM0_A3 || props.SOV_A3 || '';
        return iso;
    }

    pointInPolygon(point, polygon) {
        const x = point[0], y = point[1];
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i][0], yi = polygon[i][1];
            const xj = polygon[j][0], yj = polygon[j][1];
            if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
                inside = !inside;
            }
        }
        return inside;
    }

    pointInGeometry(point, geometry) {
        if (geometry.type === 'Polygon') {
            return this.pointInPolygon(point, geometry.coordinates[0]);
        } else if (geometry.type === 'MultiPolygon') {
            for (const poly of geometry.coordinates) {
                if (this.pointInPolygon(point, poly[0])) return true;
            }
        }
        return false;
    }

    getDistrictCentroid(feature) {
        try {
            const geom = feature.geometry;
            let ring;
            if (geom.type === 'Polygon') ring = geom.coordinates[0];
            else if (geom.type === 'MultiPolygon') ring = geom.coordinates[0][0];
            if (!ring || ring.length === 0) return null;
            let sumX = 0, sumY = 0;
            for (const coord of ring) {
                sumX += coord[0];
                sumY += coord[1];
            }
            return [sumX / ring.length, sumY / ring.length];
        } catch (e) { return null; }
    }

    // --- Rendering ---

    renderLayer(data, level, parentISO = '') {
        if (this.currentLayer) this.map.removeLayer(this.currentLayer);

        this.currentLevel = level;
        this.currentParentISO = parentISO;

        let targetCapital = null;
        const capitals = this.data.getCapitalData();

        if (level === 1 && capitals.countries) {
            targetCapital = capitals.countries[parentISO];
        } else if (level === 2 && capitals.states && capitals.states[parentISO]) {
            targetCapital = Object.values(capitals.states[parentISO]).map(c => ({ lat: c.lat, lng: c.lng }));
        }

        this.currentStyleContext = {
            level,
            parentISO,
            targetCapital
        };

        this.currentLayer = L.geoJSON(data, {
            style: (feature) => this.getBaseStyle(feature),
            onEachFeature: (feature, layer) => {
                const props = feature.properties;
                const name = this.getName(props);
                const iso = this.getISO(props, parentISO);
                const stateCode = props.shapeISO || '';

                layer.bindTooltip(name, { sticky: true, direction: 'top', offset: [0, -10] });

                layer.on('mouseover', () => {
                    if (this.castVisible && this.currentLevel === 1) {
                        const castStyle = this.getCastStyleForFeature(feature);
                        layer.setStyle({
                            fillColor: castStyle.fillColor,
                            fillOpacity: castStyle.fillOpacity,
                            weight: 2.5,
                            color: '#1a1a2e'
                        });
                    } else {
                        layer.setStyle({ weight: 2.5, color: '#1a1a2e', fillOpacity: 0.85 });
                    }
                    layer.bringToFront();
                });
                layer.on('mouseout', () => {
                    if (this.currentLayer) {
                        if (this.castVisible && this.currentLevel === 1) {
                            // Issue was here: resetStyle() re-applies base (white) styles and wiped CAST colors.
                            layer.setStyle(this.getCastStyleForFeature(feature));
                        } else {
                            this.currentLayer.resetStyle(layer);
                        }
                    }
                });
                layer.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    this.handleClick(feature, layer, level, iso, name, stateCode);
                });
            }
        }).addTo(this.map);

        if (level === 1) {
            this.buildAdminLookup();
        } else {
            this.admin1Lookup = null;
        }

        if (this.castVisible) {
            this.applyCastChoropleth();
        }
    }

    renderNeighbors(centerISO) {
        if (this.neighborsLayer) this.map.removeLayer(this.neighborsLayer);
        this.neighborsLayer = L.layerGroup();

        const info = this.data.getCountryInfo(centerISO);
        // We need access to worldData features. 
        // In DataManager, we only stored configs. World GeoJSON was fetched in init().
        // Let's re-fetch or cache worldData in DataManager properly? 
        // For now, let's fetch 'world' from cache via data manager since we loaded it in init().
        const worldData = this.data.cache['world'];

        if (!info || !info.neighbors || !worldData) return;

        const neighborFeatures = worldData.features.filter(f => {
            return info.neighbors.includes(this.getISO(f.properties));
        });

        if (neighborFeatures.length > 0) {
            L.geoJSON(neighborFeatures, {
                style: {
                    color: '#64748b', weight: 1.5, fillOpacity: 0,
                    dashArray: '4, 4', opacity: 0.6
                },
                onEachFeature: (feature, layer) => {
                    layer.bindTooltip(this.getName(feature.properties), {
                        permanent: true, direction: 'center', className: 'neighbor-label'
                    });
                    layer.options.interactive = false;
                }
            }).addTo(this.neighborsLayer);
            this.neighborsLayer.addTo(this.map);
        }
    }

    async handleClick(feature, layer, level, iso, name, stateCode) {
        const bounds = layer.getBounds();
        const sources = this.data.countrySources;

        if (level === 0) {
            // Country -> State
            const hasADM1 = sources[iso] && sources[iso].adm1;
            window.dispatchEvent(new CustomEvent('live-tracker-region-change', {
                detail: { level, iso, geometry: feature.geometry || null }
            }));
            this.ui.showPanel(name, iso, 0, this.data.getCountryInfo(iso), this.data.getVolatileData(iso), this.data.currencyRates);

            if (hasADM1) {
                this.ui.showLoader(`Loading ${name} states...`);
                const data = await this.data.fetchJSON(sources[iso].adm1, `${iso}_ADM1`);
                this.ui.hideLoader();

                if (data && data.features && data.features.length > 0) {
                    this.isNavigating = true;
                    this.renderNeighbors(iso);
                    this.renderLayer(data, 1, iso);
                    this.navStack.push({ name, iso, level: 1, bounds });

                    // Trigger EVENT for InteractionManager to hide layers
                    window.dispatchEvent(new CustomEvent('map-level-change', { detail: { level: 1 } }));

                    this.map.fitBounds(bounds, { padding: [40, 40], animate: true });
                    this.renderBreadcrumb();
                    setTimeout(() => { this.isNavigating = false; }, 500);
                } else {
                    this.ui.toast('No state data available');
                }
            }
        } else if (level === 1) {
            // State -> District
            const hasADM2 = sources[iso] && sources[iso].adm2;
            window.dispatchEvent(new CustomEvent('live-tracker-region-change', {
                detail: { level, iso, geometry: feature.geometry || null }
            }));
            this.ui.showPanel(name, stateCode || iso, 1, null, null, null, { countryIso: iso });

            if (hasADM2) {
                this.ui.showLoader(`Loading ${name} districts...`);
                const data = await this.data.fetchJSON(sources[iso].adm2, `${iso}_ADM2`);
                this.ui.hideLoader();

                if (data && data.features) {
                    // Filter districts
                    const filtered = data.features.filter(f => {
                        const centroid = this.getDistrictCentroid(f);
                        return centroid && this.pointInGeometry(centroid, feature.geometry);
                    });

                    if (filtered.length > 0) {
                        this.isNavigating = true;
                        this.renderLayer({ type: 'FeatureCollection', features: filtered }, 2, iso);
                        this.navStack.push({ name, iso, level: 2, bounds, stateCode });

                        window.dispatchEvent(new CustomEvent('map-level-change', { detail: { level: 2 } }));

                        this.map.fitBounds(bounds, { padding: [40, 40], animate: true });
                        this.renderBreadcrumb();
                        setTimeout(() => { this.isNavigating = false; }, 500);
                    } else {
                        this.ui.toast('No district data for this region');
                    }
                }
            }
        } else {
            window.dispatchEvent(new CustomEvent('live-tracker-region-change', {
                detail: { level, iso, geometry: feature.geometry || null }
            }));
            this.ui.showPanel(name, stateCode || iso, 2, null, null, null, { countryIso: iso });
        }
    }

    renderBreadcrumb() {
        const container = document.getElementById('breadcrumb');
        container.innerHTML = '';
        this.navStack.forEach((item, idx) => {
            if (idx > 0) {
                const sep = document.createElement('span');
                sep.className = 'crumb-sep';
                sep.textContent = ' / ';
                container.appendChild(sep);
            }
            const crumb = document.createElement('span');
            crumb.className = 'crumb' + (idx === this.navStack.length - 1 ? ' active' : '');
            crumb.textContent = item.name;
            if (idx < this.navStack.length - 1) crumb.onclick = () => this.navigateTo(idx);
            container.appendChild(crumb);
        });
    }

    async navigateTo(idx) {
        this.navStack = this.navStack.slice(0, idx + 1);
        const current = this.navStack[idx];
        this.ui.showLoader('Loading...');
        this.ui.hidePanel();

        if (current.level === 0) {
            const data = await this.data.fetchJSON('data/countries.geojson', 'world');
            this.ui.hideLoader();
            this.renderLayer(data, 0);

            window.dispatchEvent(new CustomEvent('map-level-change', { detail: { level: 0 } }));
            window.dispatchEvent(new CustomEvent('live-tracker-region-change', {
                detail: { level: 0, iso: '', geometry: null }
            }));

            if (this.neighborsLayer) this.map.removeLayer(this.neighborsLayer);
            this.map.setView([20, 0], 2, { animate: true });
        } else if (current.level === 1) {
            const data = await this.data.fetchJSON(this.data.countrySources[current.iso].adm1, `${current.iso}_ADM1`);
            this.ui.hideLoader();
            if (data) {
                this.renderNeighbors(current.iso);
                this.renderLayer(data, 1, current.iso);
                window.dispatchEvent(new CustomEvent('map-level-change', { detail: { level: 1 } }));
                window.dispatchEvent(new CustomEvent('live-tracker-region-change', {
                    detail: { level: 1, iso: current.iso, geometry: null }
                }));
                if (current.bounds) this.map.fitBounds(current.bounds, { padding: [40, 40] });
            }
        }
        this.renderBreadcrumb();
    }

    getBaseStyle(feature) {
        const props = feature.properties || {};
        const name = this.getName(props);
        const iso = this.getISO(props, this.currentParentISO);

        let fillColor = '#ffffff';
        let fillOpacity = 0.7;
        const isCapital = this.isCapitalFeature(feature);

        if (isCapital) {
            fillColor = '#ef4444';
            fillOpacity = 0.9;
        }

        return {
            fillColor: fillColor,
            weight: isCapital ? 2 : 1.2,
            opacity: 1,
            color: isCapital ? '#b91c1c' : '#e5e7eb',
            fillOpacity: fillOpacity
        };
    }

    isCapitalFeature(feature) {
        const targetCapital = this.currentStyleContext?.targetCapital;
        if (!targetCapital) return false;

        if (Array.isArray(targetCapital)) {
            for (const cap of targetCapital) {
                if (this.pointInGeometry([cap.lng, cap.lat], feature.geometry)) {
                    feature.properties.__isCapital = true;
                    return true;
                }
            }
        } else {
            if (this.pointInGeometry([targetCapital.lng, targetCapital.lat], feature.geometry)) {
                feature.properties.__isCapital = true;
                return true;
            }
        }
        feature.properties.__isCapital = false;
        return false;
    }

    normalizeAdminName(value) {
        if (!value) return '';
        return String(value)
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/&/g, 'and')
            .replace(/[^a-z0-9]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    stripAdminWords(norm) {
        if (!norm) return '';
        const adminWords = new Set([
            'and', 'of', 'the', 'state', 'states', 'province', 'region', 'district', 'county',
            'department', 'republic', 'kingdom', 'autonomous', 'territory', 'territories',
            'city', 'municipality', 'metropolitan', 'governorate', 'oblast', 'krai', 'prefecture',
            'special', 'capital', 'union', 'ut', 'nct', 'island', 'islands', 'isle', 'federal',
            'nation', 'area', 'division', 'zone', 'canton', 'commune', 'municipio', 'departamento'
        ]);
        return norm
            .split(' ')
            .filter(token => token && !adminWords.has(token))
            .join(' ');
    }

    normalizeToken(token) {
        if (!token) return '';
        const map = {
            'st': 'saint',
            'saint': 'saint',
            'mt': 'mount',
            'mount': 'mount',
            'ft': 'fort',
            'fort': 'fort',
            'n': 'north',
            's': 'south',
            'e': 'east',
            'w': 'west',
            'ne': 'northeast',
            'nw': 'northwest',
            'se': 'southeast',
            'sw': 'southwest'
        };
        return map[token] || token;
    }

    expandToken(token) {
        const normalized = this.normalizeToken(token);
        if (!normalized) return [];
        const expansions = [normalized];
        const compound = {
            northeast: ['north', 'east'],
            northwest: ['north', 'west'],
            southeast: ['south', 'east'],
            southwest: ['south', 'west']
        };
        if (compound[normalized]) {
            expansions.push(...compound[normalized]);
        }
        return expansions;
    }

    getAdminTokens(value) {
        const norm = this.normalizeAdminName(value);
        const stripped = this.stripAdminWords(norm);
        const rawTokens = stripped.split(' ').filter(Boolean);
        const tokens = [];
        rawTokens.forEach((token) => {
            this.expandToken(token).forEach((t) => {
                if (t) tokens.push(t);
            });
        });
        return Array.from(new Set(tokens));
    }

    tokenKeyFromTokens(tokens) {
        return [...tokens].sort().join('|');
    }

    buildAdminLookup() {
        if (!this.currentLayer) return;
        const entries = [];
        const variants = new Map();

        this.currentLayer.eachLayer((layer) => {
            const feature = layer.feature;
            if (!feature) return;
            const name = this.getName(feature.properties);
            const norm = this.normalizeAdminName(name);
            if (!norm) return;
            const stripped = this.stripAdminWords(norm);
            const tokens = this.getAdminTokens(name);
            const tokenKey = this.tokenKeyFromTokens(tokens);

            entries.push({ norm, stripped, tokens, tokenKey, name });

            const addVariant = (variant) => {
                if (!variant) return;
                if (!variants.has(variant)) variants.set(variant, new Set());
                variants.get(variant).add(norm);
            };

            addVariant(norm);
            addVariant(stripped);
            addVariant(norm.replace(/\s+/g, ''));
            if (stripped) addVariant(stripped.replace(/\s+/g, ''));
            if (tokenKey) addVariant(tokenKey);
        });

        this.admin1Lookup = { entries, variants };
    }

    resolveAdminName(name) {
        if (!name || !this.admin1Lookup) return null;
        const norm = this.normalizeAdminName(name);
        if (!norm) return null;
        const stripped = this.stripAdminWords(norm);
        const tokens = this.getAdminTokens(name);
        const tokenKey = this.tokenKeyFromTokens(tokens);

        const variantsToCheck = [
            norm,
            stripped,
            norm.replace(/\s+/g, ''),
            stripped.replace(/\s+/g, ''),
            tokenKey
        ].filter(Boolean);

        for (const variant of variantsToCheck) {
            const matches = this.admin1Lookup.variants.get(variant);
            if (matches && matches.size === 1) {
                return Array.from(matches)[0];
            }
        }

        // Fuzzy fallback with conservative thresholds.
        let best = null;
        let bestScore = 0;
        let secondScore = 0;
        const tokenSet = new Set(tokens);

        const similarity = (a, b) => {
            if (!a || !b) return 0;
            const la = a.length;
            const lb = b.length;
            const dp = Array.from({ length: la + 1 }, () => Array(lb + 1).fill(0));
            for (let i = 0; i <= la; i++) dp[i][0] = i;
            for (let j = 0; j <= lb; j++) dp[0][j] = j;
            for (let i = 1; i <= la; i++) {
                for (let j = 1; j <= lb; j++) {
                    const cost = a[i - 1] === b[j - 1] ? 0 : 1;
                    dp[i][j] = Math.min(
                        dp[i - 1][j] + 1,
                        dp[i][j - 1] + 1,
                        dp[i - 1][j - 1] + cost
                    );
                }
            }
            const dist = dp[la][lb];
            const maxLen = Math.max(la, lb);
            return maxLen === 0 ? 0 : 1 - dist / maxLen;
        };

        this.admin1Lookup.entries.forEach((entry) => {
            if (!entry.tokens || entry.tokens.length === 0) return;
            const entrySet = new Set(entry.tokens);
            let intersection = 0;
            tokenSet.forEach((t) => {
                if (entrySet.has(t)) intersection += 1;
            });
            const union = new Set([...tokenSet, ...entrySet]).size;
            const jaccard = union > 0 ? intersection / union : 0;
            if (jaccard < 0.5) return;
            const sim = similarity(stripped || norm, entry.stripped || entry.norm);
            const score = (0.6 * jaccard) + (0.4 * sim);
            if (score > bestScore) {
                secondScore = bestScore;
                bestScore = score;
                best = entry.norm;
            } else if (score > secondScore) {
                secondScore = score;
            }
        });

        if (bestScore >= 0.82 && bestScore - secondScore >= 0.08) {
            return best;
        }
        return null;
    }

    getCastColor(value, colors) {
        const safeValue = Math.max(0, Math.round(Number(value) || 0));
        if (safeValue <= 0) return colors[0];
        const idx = Math.min(safeValue, colors.length - 1);
        return colors[idx];
    }

    buildCastScale(maxValue) {
        const max = Math.max(1, Math.round(Number(maxValue) || 1));
        const colors = ['#ffffff'];
        const start = [219, 234, 254]; // #dbeafe
        const end = [30, 58, 138];     // #1e3a8a
        for (let i = 1; i <= max; i++) {
            const t = max === 1 ? 1 : (i - 1) / (max - 1);
            const r = Math.round(start[0] + (end[0] - start[0]) * t);
            const g = Math.round(start[1] + (end[1] - start[1]) * t);
            const b = Math.round(start[2] + (end[2] - start[2]) * t);
            colors.push(`rgb(${r}, ${g}, ${b})`);
        }
        return colors;
    }

    getCastStyleForFeature(feature) {
        const baseStyle = this.getBaseStyle(feature);
        if (!this.castScale || !this.castScale.admin1Totals) return baseStyle;
        const name = this.normalizeAdminName(this.getName(feature.properties));
        if (!this.castScale.admin1Totals.has(name)) return baseStyle;
        const value = this.castScale.admin1Totals.get(name) || 0;
        if (value <= 0) return baseStyle;
        const fillColor = this.getCastColor(value, this.castScale.colors);
        return {
            ...baseStyle,
            fillColor,
            fillOpacity: 0.75
        };
    }

    applyCastChoropleth() {
        if (!this.castVisible) return;
        if (!this.castData || !this.currentLayer) return;
        if (this.currentLevel !== 1) return;

        if (!this.admin1Lookup) {
            this.buildAdminLookup();
        }

        // Reset to clean base before applying new month colors.
        this.currentLayer.setStyle((feature) => this.getBaseStyle(feature));

        const rows = this.castData.rows || [];
        if (!Array.isArray(rows) || rows.length === 0) return;

        const values = [];
        const admin1Totals = new Map();
        rows.forEach((row) => {
            const resolved = this.resolveAdminName(row.admin1);
            const total = Number(row.total) || 0;
            if (!resolved) return;
            const current = admin1Totals.get(resolved) || 0;
            const next = current + total;
            admin1Totals.set(resolved, next);
        });

        admin1Totals.forEach((v) => {
            if (v > 0) values.push(v);
        });

        if (values.length === 0) {
            this.clearCastChoropleth();
            return;
        }

        const maxValue = Math.max(...values);
        const colors = this.buildCastScale(maxValue);
        this.castScale = { admin1Totals, colors };

        this.currentLayer.eachLayer((layer) => {
            const feature = layer.feature;
            if (!feature) return;
            const isCapital = feature.properties?.__isCapital === true || this.isCapitalFeature(feature);
            if (isCapital) {
                layer.setStyle(this.getBaseStyle(feature));
                return;
            }
            const name = this.normalizeAdminName(this.getName(feature.properties));
            if (!admin1Totals.has(name)) {
                layer.setStyle(this.getBaseStyle(feature));
                return;
            }
            const value = admin1Totals.get(name) || 0;
            if (value <= 0) {
                layer.setStyle(this.getBaseStyle(feature));
                return;
            }
            const fillColor = this.getCastColor(value, colors);
            const baseStyle = this.getBaseStyle(feature);
            layer.setStyle({
                ...baseStyle,
                fillColor,
                fillOpacity: 0.75
            });
        });
    }

    clearCastChoropleth() {
        if (this.currentLayer) {
            this.currentLayer.setStyle((feature) => this.getBaseStyle(feature));
        }
        this.castScale = null;
    }
}
