import L from 'leaflet';
import { API_BASE } from '../config.js';

export class InteractionManager {
    constructor(map, dataManager, uiManager) {
        this.map = map;
        this.data = dataManager;
        this.ui = uiManager;
        this.layers = {}; // { catId: L.layerGroup }
        this.manifest = null;

        // Hardcoded coords from app.js (Move to JSON later ideally)
        this.COUNTRY_COORDS = {
            'IND': [20.5937, 78.9629], 'PAK': [30.3753, 69.3451], 'CHN': [35.8617, 104.1954],
            'UKR': [48.3794, 31.1656], 'RUS': [61.524, 105.3188], 'TWN': [23.6978, 120.9605],
            'VNM': [14.0583, 108.2772], 'PHL': [12.8797, 121.774], 'MYS': [4.2105, 101.9758],
            'BRN': [4.5353, 114.7277], 'ISR': [31.0461, 34.8516], 'IRN': [32.4279, 53.6880], 'SYR': [34.8021, 38.9968],
            'MAR': [31.7917, -7.0926], 'ESH': [24.2155, -12.8858], 'GBR': [55.3781, -3.436],
            'ARG': [-38.4161, -63.6167], 'JPN': [36.2048, 138.2529], 'GEO': [42.3154, 43.3569],
            'MDA': [47.4116, 28.3699], 'AZE': [40.1431, 47.5769], 'ARM': [40.0691, 45.0382],
            'CYP': [35.1264, 33.4299], 'TUR': [38.9637, 35.2433], 'KOR': [35.9078, 127.7669],
            'PSE': [31.9522, 35.2332], 'USA': [37.0902, -95.7129], 'CAN': [56.1304, -106.3468],
            'MEX': [23.6345, -102.5528], 'BRA': [-14.235, -51.9253], 'DEU': [51.1657, 10.4515],
            'FRA': [46.2276, 2.2137], 'ZAF': [-30.5595, 22.9375], 'AUS': [-25.2744, 133.7751],
            'NZL': [-40.9006, 174.886], 'THA': [15.87, 100.9925], 'SGP': [1.3521, 103.8198],
            'IDN': [-0.7893, 113.9213], 'KHM': [12.5657, 104.991], 'LAO': [19.8563, 102.4955],
            'MMR': [21.9162, 95.956], 'ARE': [23.4241, 53.8478], 'BHR': [26.0667, 50.5577],
            'SDN': [12.8628, 30.2176], 'FIN': [61.9241, 25.7482], 'SWE': [60.1282, 18.6435],
            'PRK': [40.3399, 127.5101], 'VEN': [6.4238, -66.5897], 'LBN': [33.8547, 35.8623],
            'GRD': [12.1165, -61.6790], 'ESP': [40.4637, -3.7492], 'ERI': [15.1794, 39.7823], 'ETH': [9.1450, 40.4897],
            'HKG': [22.3193, 114.1694]
        };

        document.addEventListener('open-panel', (e) => {
            const itemId = e.detail != null ? String(e.detail) : '';
            if (!itemId || itemId === 'undefined' || !this.registry || !this.registry[itemId]) {
                this.ui.toast('Event details unavailable', 'info');
                return;
            }
            this.map.closePopup();
            this.ui.showDisputePanel(this.registry[itemId], (iso) => this.data.getCountryInfo(iso));
        });

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.popup-btn');
            if (!btn || !btn.dataset.itemId) return;
            e.preventDefault();
            document.dispatchEvent(new CustomEvent('open-panel', { detail: btn.dataset.itemId }));
        });

        // Listen for map level changes to auto-hide/show
        window.addEventListener('map-level-change', (e) => {
            this.updateVisibility(e.detail.level);
        });
    }

    _getCategoryItems(catId) {
        if (!this.manifest) return [];
        if (this.manifest.interactionsById && this.manifest.byCategory) {
            const ids = this.manifest.byCategory[catId] || [];
            return ids.map(id => this.manifest.interactionsById[id]).filter(Boolean);
        }
        return (this.manifest.interactions && this.manifest.interactions[catId]) ? this.manifest.interactions[catId] : [];
    }

    async init() {
        this.manifest = await this.data.fetchJSON('data/interactions/manifest.json');
        if (!this.manifest) return;

        if (!this.map.getPane('interactionPane')) {
            this.map.createPane('interactionPane');
            this.map.getPane('interactionPane').style.zIndex = 450;
        }

        this.registry = {}; // Stores all interaction objects by ID
        this.categoryData = {}; // Stores { visual, hit, type } list per category

        this.renderPanelControls();

        for (const [catId, catData] of Object.entries(this.manifest.categories)) {
            const interactions = this._getCategoryItems(catId);

            this.layers[catId] = L.layerGroup();
            this.categoryData[catId] = [];

            interactions.forEach(item => {
                this.registry[item.id] = item;
                this.renderInteraction(item, catData, catId);
            });

            this.updateInteractionVisibility(catId);
        }
    }

    getInteractionByDescription(nameOrDescription, descriptionOptional) {
        const a = (nameOrDescription || '').toString().trim().toLowerCase();
        const b = (descriptionOptional != null ? descriptionOptional : nameOrDescription || '').toString().trim().toLowerCase();
        const search = a.length >= b.length ? a : b;
        if (!search || !this.registry) return null;
        for (const item of Object.values(this.registry)) {
            const iname = (item.name || '').toLowerCase();
            const idesc = (item.description || '').toLowerCase();
            if (search.length >= 2 && (iname.includes(search) || idesc.includes(search) || search.includes(iname))) return item;
        }
        return null;
    }

    renderPanelControls() {
        const container = document.getElementById('interactions-panel');
        if (!container) return;

        // Preserve Firehose DOM (LIVE tracker) across re-renders
        const existingFirehoseBody = document.getElementById('firehose-body');
        const preservedFirehoseNodes = existingFirehoseBody ? Array.from(existingFirehoseBody.childNodes) : [];

        container.innerHTML = `
            <div class="interaction-section">
                <div class="interaction-section-title">Firehose</div>
                <div class="interaction-section-body" id="firehose-body"></div>
            </div>
            <div class="interaction-section">
                <div class="interaction-section-title" style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
                    <span>Interactions</span>
                    <button class="interaction-refresh-btn" id="interactions-refresh">Refresh (GDELT)</button>
                </div>
                <div class="interaction-section-body" id="interaction-body"></div>
            </div>
        `;

        const newFirehoseBody = document.getElementById('firehose-body');
        if (newFirehoseBody && preservedFirehoseNodes.length) {
            preservedFirehoseNodes.forEach(node => newFirehoseBody.appendChild(node));
        }


        // Toggle handler for panel header (collapse)
        const header = document.getElementById('interactions-header');
        if (header) {
            // Clone to remove old listeners
            const newHeader = header.cloneNode(true);
            header.parentNode.replaceChild(newHeader, header);
            newHeader.addEventListener('click', () => {
                const controls = document.querySelector('.map-controls');
                if (controls) controls.classList.toggle('collapsed');
            });
        }

        const interactionBody = document.getElementById('interaction-body') || container;

        const refreshBtn = document.getElementById('interactions-refresh');
        if (refreshBtn) {
            refreshBtn.onclick = async (e) => {
                e.preventDefault();
                refreshBtn.disabled = true;
                refreshBtn.textContent = 'Refreshing...';
                try {
                    const res = await fetch(`${API_BASE}/api/interactions/process-gdelt`, { method: 'POST' });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    await this.refreshManifestAndRerender();
                    this.ui.toast('Interactions refreshed', 'success');
                } catch (err) {
                    console.error(err);
                    this.ui.toast('Refresh failed', 'error');
                } finally {
                    refreshBtn.disabled = false;
                    refreshBtn.textContent = 'Refresh (GDELT)';
                }
            };
        }

        for (const [catId, catData] of Object.entries(this.manifest.categories)) {
            const items = this._getCategoryItems(catId);
            if (!items || items.length === 0) continue;

            const groupDiv = document.createElement('div');
            groupDiv.className = 'category-group';
            groupDiv.dataset.category = catId;

            const toggleHtml = `
                <label class="control-toggle">
                    <input type="checkbox" id="toggle-${catId}" ${catId === 'disputes' ? 'checked' : ''}>
                    <div class="toggle-label">
                        <span class="category-dot"></span>
                        ${catData.name}
                    </div>
                    <div class="toggle-actions">
                        <span class="toggle-count ${items.length > 0 ? 'has-items' : ''}" id="count-${catId}">${items.length}</span>
                        ${items.length > 0 ? `<span class="btn-expand" id="expand-${catId}" title="Show Subtypes">▼</span>` : ''}
                    </div>
                </label>
                <div class="subtypes-list" id="subtypes-${catId}"></div>
            `;
            groupDiv.innerHTML = toggleHtml;
            interactionBody.appendChild(groupDiv);

            // Subtypes UI
            const subtypesList = groupDiv.querySelector(`#subtypes-${catId}`);
            const availableSubtypes = catData.subtypes || [];

            if (items.length > 0) {
                availableSubtypes.forEach(subtype => {
                    const count = items.filter(i => (i.subtype || i.type) === subtype).length;
                    if (!count) return;
                    const subId = `toggle-${catId}-${subtype}`;

                    const subItem = document.createElement('label');
                    subItem.className = 'subtype-item';
                    subItem.innerHTML = `
                        <input type="checkbox" id="${subId}" checked data-cat="${catId}" data-sub="${subtype}">
                        <span class="subtype-label">${subtype.replace(/_/g, ' ')} <span style="font-size:9px;color:#999">(${count})</span></span>
                     `;
                    subtypesList.appendChild(subItem);

                    // Subtype change listener
                    subItem.querySelector('input').addEventListener('change', () => {
                        this.updateInteractionVisibility(catId);
                    });
                });

                // Expand/Collapse logic
                const expandBtn = groupDiv.querySelector(`#expand-${catId}`);
                if (expandBtn) {
                    expandBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        subtypesList.classList.toggle('expanded');
                        expandBtn.textContent = subtypesList.classList.contains('expanded') ? '▲' : '▼';
                    });
                }
            }

            // Main Toggle Listener
            const mainToggle = groupDiv.querySelector(`#toggle-${catId}`);
            mainToggle.addEventListener('change', (e) => {
                const isChecked = e.target.checked;
                const inputs = subtypesList.querySelectorAll('input');
                inputs.forEach(i => i.checked = isChecked);
                this.updateInteractionVisibility(catId);
            });
        }
    }

    async refreshManifestAndRerender() {
        for (const layer of Object.values(this.layers || {})) {
            try {
                if (layer && this.map.hasLayer(layer)) this.map.removeLayer(layer);
            } catch (_) { }
        }

        this.layers = {};
        this.registry = {};
        this.categoryData = {};

        this.manifest = await this.data.fetchJSON(`data/interactions/manifest.json?t=${Date.now()}`);
        if (!this.manifest) return;

        this.renderPanelControls();

        for (const [catId, catData] of Object.entries(this.manifest.categories)) {
            const interactions = this._getCategoryItems(catId);
            this.layers[catId] = L.layerGroup();
            this.categoryData[catId] = [];
            interactions.forEach(item => {
                this.registry[item.id] = item;
                this.renderInteraction(item, catData, catId);
            });
            this.updateInteractionVisibility(catId);
        }
    }

    updateInteractionVisibility(catId) {
        const toggle = document.getElementById(`toggle-${catId}`);
        const layerGroup = this.layers[catId];
        const dataItems = this.categoryData[catId];

        if (!toggle || !layerGroup || !dataItems) return;

        layerGroup.clearLayers();

        if (!toggle.checked) {
            if (this.map.hasLayer(layerGroup)) this.map.removeLayer(layerGroup);
            return;
        }

        const catData = this.manifest?.categories?.[catId];
        const availableSubtypes = (catData?.subtypes || []).slice();
        const container = document.getElementById(`subtypes-${catId}`);
        const hasSubtypeFilters = availableSubtypes.length > 0 && container;
        const checkedSubtypes = hasSubtypeFilters
            ? Array.from(container.querySelectorAll('input:checked')).map(input => input.dataset.sub).filter(Boolean)
            : [];

        for (const item of dataItems) {
            if (!hasSubtypeFilters) {
                layerGroup.addLayer(item.visual);
                layerGroup.addLayer(item.hit);
                continue;
            }
            const itemSubtype = item.subtype ?? item.type;
            const inSubtypeList = availableSubtypes.includes(itemSubtype);
            if (!inSubtypeList) {
                layerGroup.addLayer(item.visual);
                layerGroup.addLayer(item.hit);
                continue;
            }
            if (checkedSubtypes.length === 0) continue;
            if (!checkedSubtypes.includes(itemSubtype)) continue;
            layerGroup.addLayer(item.visual);
            layerGroup.addLayer(item.hit);
        }

        if (!this.map.hasLayer(layerGroup)) this.map.addLayer(layerGroup);
    }

    updateVisibility(level) {
        for (const catId of Object.keys(this.layers)) {
            const toggle = document.getElementById(`toggle-${catId}`);
            const layer = this.layers[catId];
            if (!toggle || !layer) continue;

            // Only show at World Level (0) IF checked
            if (level === 0 && toggle.checked) {
                if (!this.map.hasLayer(layer)) this.map.addLayer(layer);
            } else {
                if (this.map.hasLayer(layer)) this.map.removeLayer(layer);
            }
        }
    }

    renderInteraction(item, catData, catId) {
        const vizType = item.visualization_type || 'geodesic';
        if (vizType === 'dot') {
            const loc = item.location;
            let latlng = null;
            if (loc && typeof loc.lat === 'number' && typeof loc.lon === 'number') {
                latlng = [loc.lat, loc.lon];
            } else if (loc && loc.iso && this.COUNTRY_COORDS[loc.iso]) {
                latlng = this.COUNTRY_COORDS[loc.iso];
            }
            if (latlng) this.drawDot(latlng, item, catData, catId);
            return;
        }
        const participants = item.participants || [];
        if (participants.length === 0) return;
        const coords = participants.map(p => this.COUNTRY_COORDS[p]).filter(Boolean);
        if (coords.length < 2) return;
        const arcStyle = item.arc_style || catData.arc_style || 'solid';
        for (let i = 0; i < coords.length; i++) {
            for (let j = i + 1; j < coords.length; j++) {
                this.drawCurve(coords[i], coords[j], item, catData, catId, arcStyle);
            }
        }
    }

    drawDot(latlng, item, catData, catId) {
        const color = catData.color || '#6b7280';
        const marker = L.circleMarker(latlng, {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            fillOpacity: 0.9,
            pane: 'interactionPane',
        });
        const hit = L.circleMarker(latlng, {
            radius: 15,
            fillColor: 'transparent',
            color: 'transparent',
            pane: 'interactionPane',
            className: `interaction-hit-${item.id}`,
        });
        hit.bindPopup(this._popupContent(item, catData));
        hit.on('mouseover', () => marker.setStyle({ radius: 10 }));
        hit.on('mouseout', () => marker.setStyle({ radius: 8 }));
        this.categoryData[catId].push({ visual: marker, hit: hit, type: item.type, subtype: item.subtype });
    }

    _popupContent(item, catData) {
        const itemId = item.id != null ? String(item.id) : '';
        const safeId = itemId.replace(/"/g, '&quot;').replace(/</g, '&lt;');
        return `
            <div class="popup-content">
                <div class="popup-title">${catData.icon || ''} ${item.name}</div>
                <div class="popup-type">${item.type || ''}</div>
                <button type="button" class="popup-btn" data-item-id="${safeId}">More Details</button>
            </div>
        `;
    }

    drawCurve(start, end, item, catData, catId, arcStyle) {
        const latlngs = this.createGeodesicArc(start, end, 20);
        const dashArray = arcStyle === 'dashed' ? '5, 5' : (arcStyle === 'dotted' ? '2, 4' : null);

        const ghost = L.polyline(latlngs, {
            color: 'transparent',
            weight: 15,
            pane: 'interactionPane',
            className: `interaction-hit-${item.id}`
        });

        const visual = L.polyline(latlngs, {
            color: catData.color,
            weight: 2,
            dashArray: dashArray,
            pane: 'interactionPane',
            className: `interaction-arc-${item.id}`,
            interactive: false
        });

        ghost.bindPopup(this._popupContent(item, catData));
        ghost.on('mouseover', () => visual.setStyle({ weight: 4, opacity: 1 }));
        ghost.on('mouseout', () => visual.setStyle({ weight: 2, opacity: 0.8 }));
        this.categoryData[catId].push({
            visual: visual,
            hit: ghost,
            type: item.type,
            subtype: item.subtype
        });
    }

    createGeodesicArc(start, end, numPoints = 20) {
        const points = [];
        let lat1 = start[0], lon1 = start[1];
        let lat2 = end[0], lon2 = end[1];

        // --- IDL Handling ---
        if (lon1 - lon2 > 180) {
            lon2 += 360;
        } else if (lon2 - lon1 > 180) {
            lon1 += 360;
        }

        // --- Control Point Calculation (Quadratic Bezier) ---
        const midLat = (lat1 + lat2) / 2;
        const midLon = (lon1 + lon2) / 2;

        const dx = lon2 - lon1;
        const dy = lat2 - lat1;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Curvature factor
        const curvatureFactor = 0.25;
        let ctrlLat = midLat + (dist * curvatureFactor);
        const ctrlLon = midLon;

        // Clamp latitude
        if (ctrlLat > 85) ctrlLat = 85;
        if (ctrlLat < -85) ctrlLat = -85;

        // --- Generate Curve Points ---
        for (let i = 0; i <= numPoints; i++) {
            const t = i / numPoints;
            const invT = 1 - t;

            // Quadratic Bezier Formula
            const part1Lat = invT * invT * lat1;
            const part2Lat = 2 * invT * t * ctrlLat;
            const part3Lat = t * t * lat2;
            const lat = part1Lat + part2Lat + part3Lat;

            const part1Lon = invT * invT * lon1;
            const part2Lon = 2 * invT * t * ctrlLon;
            const part3Lon = t * t * lon2;
            const lon = part1Lon + part2Lon + part3Lon;

            points.push([lat, lon]);
        }
        return points;
    }
}
