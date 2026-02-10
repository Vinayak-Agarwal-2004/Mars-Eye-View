import L from 'leaflet';

export class SufferingLayer {
    constructor(map, dataManager, uiManager, interactionManager = null) {
        this.map = map;
        this.data = dataManager;
        this.ui = uiManager;
        this.interactionManager = interactionManager;
        this.layerGroup = L.layerGroup();
        this.isVisible = false;
        this.regionGeometry = null;

        // Pulse Icon Definition
        this.createPulseIcon = (color) => L.divIcon({
            className: 'pulse-icon',
            html: `<div class="dot" style="background:${color}"></div><div class="pulse" style="border-color:${color}"></div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });
    }

    async init() {
        // Create Pane for stacking control
        if (!this.map.getPane('sufferingPane')) {
            this.map.createPane('sufferingPane');
            this.map.getPane('sufferingPane').style.zIndex = 460; // Above interactions
        }

        // Add Toggle Control
        this.renderControl();

        // Initial Load (if enabled by default? Let's wait for user toggle)
        // Or auto-load if toggle is checked.
        const toggle = document.getElementById('toggle-suffering');
        if (toggle && toggle.checked) {
            await this.toggle(true);
        }

        window.addEventListener('live-tracker-region-change', (e) => {
            const detail = e.detail || {};
            this.regionGeometry = detail.geometry || null;
            if (this.isVisible) this.refresh();
        });

        // Auto-refresh every 5 mins?
        setInterval(() => {
            if (this.isVisible) this.refresh();
        }, 5 * 60 * 1000);
    }

    renderControl() {
        const container = document.getElementById('firehose-body') || document.getElementById('interactions-panel');
        if (!container) return;

        const div = document.createElement('div');
        div.className = 'control-item special-tracker';
        div.style.borderBottom = '1px solid #000';
        div.style.background = '#ffe4e6';
        div.style.display = 'flex';
        div.style.flexDirection = 'column';
        div.style.gap = '8px';
        div.style.padding = '8px';

        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <label class="control-toggle" style="margin:0;">
                    <input type="checkbox" id="toggle-suffering" checked>
                    <div class="toggle-label" style="color:#881337; font-weight:700;">
                        <span class="control-icon">🔴</span>
                        LIVE TRACKER
                    </div>
                </label>
                <div style="font-size:0.85em; font-weight:bold; color:#881337;">
                    <span id="count-suffering">0</span> Events
                </div>
            </div>
            
            <select id="filter-suffering-mode" style="width:100%; padding:4px; border-radius:4px; border:1px solid #e11d48; font-size:0.9em; background:white; margin-bottom:8px;">
                <option value="smart">✨ Smart Filter (Auto-Declutter)</option>
                <option value="all">Show All Reports</option>
                <option value="critical">Critical Only (>3 Sources)</option>
            </select>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:4px; font-size:0.8em; color:#881337;">
                <label><input type="checkbox" class="cat-filter" value="CONFLICT" checked> Conflict (Red)</label>
                <label><input type="checkbox" class="cat-filter" value="VIOLENCE" checked> Violence (Org)</label>
                <label><input type="checkbox" class="cat-filter" value="PROTEST" checked> Protest (Yel)</label>
                <label><input type="checkbox" class="cat-filter" value="CRIME" checked> Crime (Pnk)</label>
                <label><input type="checkbox" class="cat-filter" value="ACCIDENT" checked> Accident (Teal)</label>
                <label><input type="checkbox" class="cat-filter" value="DISASTER" checked> Disaster (Blu)</label>
            </div>
        `;

        container.appendChild(div);

        // Listeners
        document.getElementById('toggle-suffering').addEventListener('change', (e) => {
            this.toggle(e.target.checked);
        });
        document.getElementById('filter-suffering-mode').addEventListener('change', () => {
            if (this.isVisible) this.refresh();
        });

        // Category Checkboxes
        const checkboxes = div.querySelectorAll('.cat-filter');
        checkboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                if (this.isVisible) this.refresh();
            });
        });
    }

    async toggle(show) {
        this.isVisible = show;
        if (show) {
            await this.refresh();
            this.map.addLayer(this.layerGroup);
        } else {
            this.map.removeLayer(this.layerGroup);
        }
    }

    // Use numerical importance from backend
    getImportance(feature) {
        return feature.properties.importance || 1;
    }

    pointInPolygon(point, polygon) {
        const x = point[0];
        const y = point[1];
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i][0];
            const yi = polygon[i][1];
            const xj = polygon[j][0];
            const yj = polygon[j][1];
            const intersect = ((yi > y) !== (yj > y)) &&
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    }

    pointInGeometry(point, geometry) {
        if (!geometry || !geometry.type || !geometry.coordinates) return false;
        if (geometry.type === 'Polygon') {
            return this.pointInPolygon(point, geometry.coordinates[0]);
        }
        if (geometry.type === 'MultiPolygon') {
            for (const poly of geometry.coordinates) {
                if (this.pointInPolygon(point, poly[0])) return true;
            }
        }
        return false;
    }

    featureInRegion(feature) {
        if (!this.regionGeometry) return true;
        const geom = feature && feature.geometry;
        if (!geom || geom.type !== 'Point' || !Array.isArray(geom.coordinates)) return false;
        const coords = geom.coordinates;
        return this.pointInGeometry([coords[0], coords[1]], this.regionGeometry);
    }

    async refresh() {
        if (!this.isVisible) return;

        const latest = this.data.geoData ?? await this.data.fetchJSON('http://localhost:8000/api/live');
        const allFeatures = Array.isArray(latest?.features) ? latest.features : [];

        const sourceFeatures = this.regionGeometry
            ? allFeatures.filter(f => this.featureInRegion(f))
            : allFeatures;

        this.layerGroup.clearLayers();

        // 1. Calculate Density Map (Grid 5x5 degrees)
        const densityMap = {};
        const getGridKey = (lat, lng) => `${Math.floor(lat / 5)},${Math.floor(lng / 5)}`;

        sourceFeatures.forEach(f => {
            const coords = f.geometry.coordinates; // lng, lat
            const key = getGridKey(coords[1], coords[0]);
            densityMap[key] = (densityMap[key] || 0) + 1;
        });

        // 2. Filter
        const mode = document.getElementById('filter-suffering-mode')?.value || 'smart';

        // Get active categories
        const activeCats = Array.from(document.querySelectorAll('.cat-filter'))
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        let filteredFeatures = sourceFeatures.filter(f => {
            const props = f.properties;

            // Category Filter
            // If category is somehow missing or not in our list (like DISPLACEMENT or OTHER), 
            // maybe default to showing it or strictly hide it? 
            // Let's be lenient: if it matches a known unchecked type, hide it.
            if (activeCats.length > 0) {
                // Check if this feature's category is in the active list
                // Normalize category to uppercase just in case
                const cat = (props.category || 'OTHER').toUpperCase();

                // We only explicitly filter OUT things that have a checkbox and are unchecked.
                // But simpler: just check if it matches one of the checked values.
                // However, we have "OTHER" and "DISPLACEMENT" which might not have checkboxes yet?
                // Let's rely on the checkbox values matching the taxonomy exactly.

                // If it's one of the main types we have checkboxes for, check if it's checked.
                // Determine if this category SHOULD be filtered.
                // Actually, simpler logic: 
                // If the user UNCHECKED 'CRIME', then any feature with category 'CRIME' should be hidden.

                const mappedCheckboxes = ['CONFLICT', 'VIOLENCE', 'PROTEST', 'CRIME', 'ACCIDENT', 'DISASTER'];
                if (mappedCheckboxes.includes(cat) && !activeCats.includes(cat)) {
                    return false;
                }
            }

            const importance = this.getImportance(f);

            if (mode === 'all') return true;
            if (mode === 'critical') return importance >= 3;

            if (mode === 'smart') {
                const coords = f.geometry.coordinates;
                const density = densityMap[getGridKey(coords[1], coords[0])] || 0;

                // Adaptive Threshold:
                // If density is high (>20 events nearby), require importance >= 3
                // If density is medium (>5 nearby), require importance >= 2
                // If density is low, show everything (importance >= 1)
                if (density > 20) return importance >= 3;
                if (density > 5) return importance >= 2;
                return true;
            }
            return true;
        });

        // 3. Render
        let total = 0;

        // Sort by Date Descending first? Assuming source is sorted.
        // Actually for rendering z-index, newer on top is good.
        filteredFeatures.forEach((f, index) => {
            const props = f.properties;
            const coords = f.geometry.coordinates;
            const latlng = [coords[1], coords[0]];
            const color = props.color || '#ef4444';
            const importance = this.getImportance(f);

            let layer;
            // Only animate the very top newest/most important
            const isPulse = index < 30; // limit pulses

            if (isPulse) {
                layer = L.marker(latlng, {
                    icon: this.createPulseIcon(color),
                    pane: 'sufferingPane'
                });
            } else {
                layer = L.circleMarker(latlng, {
                    radius: 3 + (Math.min(importance, 5)), // Size based on importance
                    fillColor: color,
                    color: null,
                    weight: 0,
                    fillOpacity: 0.7,
                    pane: 'sufferingPane'
                });
            }

            layer.on('click', () => {
                this.map.flyTo(latlng, 8, {
                    animate: true,
                    duration: 0.8,
                    easeLinearity: 0.5
                });

                const namePart = props.name.split(': ')[1] || props.name;
                const descriptionText = props.html || props.description || '';
                const matched = this.interactionManager && this.interactionManager.getInteractionByDescription(props.name || '', descriptionText);
                if (matched) {
                    this.ui.showDisputePanel(matched, (iso) => this.data.getCountryInfo(iso));
                } else {
                    this.ui.showDisputePanel({
                        claimants: [namePart],
                        region: namePart || 'Unknown Location',
                        description: descriptionText || 'No additional details available.',
                        type: props.category,
                        status: 'Active (Live)',
                        since: props.timestamp || props.date || 'Just now',
                        sources: props.sources || (props.sourceurl ? [{ url: props.sourceurl, name: 'GDELT' }] : [])
                    });
                }
            });

            // Tooltip
            layer.bindTooltip(`${props.category}: ${props.name} (${importance})`, {
                offset: isPulse ? [10, 0] : [0, 0],
                permanent: false,
                direction: 'right'
            });

            this.layerGroup.addLayer(layer);
            total++;
        });

        // Update count
        const countEl = document.getElementById('count-suffering');
        if (countEl) countEl.textContent = total;
    }
}
