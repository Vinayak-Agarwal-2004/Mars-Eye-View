export class UIManager {
    constructor() {
        this.RELIGION_COLORS = {
            'Hindu': '#ff6b35', 'Muslim': '#2ecc71', 'Christian': '#3498db',
            'Buddhist': '#f39c12', 'Jewish': '#9b59b6', 'Sikh': '#e67e22',
            'Unaffiliated': '#95a5a6', 'Folk': '#1abc9c', 'Shinto': '#e74c3c',
            'Other': '#7f8c8d'
        };

        this.activeTab = 'info';
        this.latestCast = null;
        this._panelRequestId = 0;

        this.initEventListeners();
    }

    $(id) {
        return document.getElementById(id);
    }

    escapeHtml(str) {
        if (str == null || typeof str !== 'string') return '';
        const m = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
        return str.replace(/[&<>"']/g, c => m[c]);
    }

    formatAnalysisHtml(text) {
        if (!text || typeof text !== 'string') return '';
        const escaped = this.escapeHtml(text.trim());
        const paragraphs = escaped.split(/\n\n+/).filter(p => p.length > 0);
        const inner = paragraphs.length > 0
            ? paragraphs.map(p => `<p style="margin:6px 0 0;">${p.replace(/\n/g, '<br/>')}</p>`).join('')
            : `<p style="margin:6px 0 0;">${escaped}</p>`;
        return `<div class="panel-analysis-block" style="margin-top:10px; padding:10px; background:#f0f9ff; border-radius:8px; border-left:4px solid #0ea5e9; max-height:280px; overflow-y:auto;"><strong>Analysis</strong>${inner}</div>`;
    }

    initEventListeners() {
        // Tab click handlers
        document.querySelectorAll('.panel-tabs .tab').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        // Close button
        const closeBtn = this.$('panel-close');
        if (closeBtn) closeBtn.onclick = () => this.hidePanel();
    }

    showLoader(msg, progress = null) {
        const el = this.$('loader-text');
        if (el) el.textContent = msg;
        if (progress !== null && progress !== undefined) {
            this.setLoaderProgress(progress);
        }
        this.$('loader').classList.remove('hidden');
    }

    hideLoader() {
        this.$('loader').classList.add('hidden');
        this.setLoaderProgress(0);
    }

    setLoaderProgress(value) {
        const bar = this.$('loader-progress-bar');
        const text = this.$('loader-progress-text');
        const wrap = this.$('loader-progress');
        if (!bar || !text || !wrap) return;
        const clamped = Math.max(0, Math.min(1, Number(value) || 0));
        const pct = Math.round(clamped * 100);
        bar.style.width = `${pct}%`;
        text.textContent = `${pct}%`;
        wrap.style.display = 'block';
    }

    toast(msg, type = 'info') {
        const t = document.createElement('div');
        t.className = `toast toast-${type}`;
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    }

    switchTab(tabName) {
        document.querySelectorAll('.panel-tabs .tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `tab-${tabName}`);
        });

        this.activeTab = tabName;
        window.dispatchEvent(new CustomEvent('cast-tab-visibility', {
            detail: { visible: tabName === 'predictions' }
        }));

        if (tabName === 'predictions' && this.latestCast) {
            window.dispatchEvent(new CustomEvent('cast-data-update', {
                detail: this.latestCast
            }));
        }
        if (tabName === 'wiki') {
            this._maybeLoadWikiIframe();
        } else {
            const iframe = this.$('wiki-iframe');
            if (iframe) {
                iframe.style.display = 'none';
            }
        }

        this.updateCastDebugOverlay(this.latestCast);
    }

    _maybeLoadWikiIframe() {
        const iframe = this.$('wiki-iframe');
        const placeholder = this.$('wiki-tab-placeholder');
        const fallback = this.$('wiki-open-newtab');
        if (!iframe || !placeholder) return;
        const title = this._currentWikiTitle;
        if (!title) {
            iframe.style.display = 'none';
            placeholder.style.display = 'block';
            if (fallback) fallback.style.display = 'none';
            return;
        }
        const mobileUrl = `https://en.m.wikipedia.org/wiki/${encodeURIComponent(title)}`;
        if (iframe.src === mobileUrl || iframe.dataset.loaded === title) {
            placeholder.style.display = 'none';
            iframe.style.display = 'block';
            if (fallback) {
                fallback.href = this._currentWikiUrl || mobileUrl;
                fallback.style.display = 'inline-block';
            }
            return;
        }
        placeholder.textContent = 'Loading Wikipedia…';
        placeholder.style.display = 'block';
        iframe.style.display = 'none';
        iframe.onload = () => {
            placeholder.style.display = 'none';
            iframe.style.display = 'block';
            if (fallback) {
                fallback.href = this._currentWikiUrl || mobileUrl;
                fallback.style.display = 'inline-block';
            }
            iframe.dataset.loaded = title;
        };
        iframe.onerror = () => {
            placeholder.textContent = 'Could not load. ';
            placeholder.style.display = 'block';
            iframe.style.display = 'none';
            if (fallback) {
                fallback.href = this._currentWikiUrl || mobileUrl;
                fallback.style.display = 'inline-block';
            }
        };
        iframe.src = mobileUrl;
    }

    _resetWikiTab() {
        this._currentWikiTitle = null;
        this._currentWikiUrl = null;
        const iframe = this.$('wiki-iframe');
        const placeholder = this.$('wiki-tab-placeholder');
        const fallback = this.$('wiki-open-newtab');
        if (iframe) {
            iframe.src = 'about:blank';
            iframe.style.display = 'none';
            delete iframe.dataset.loaded;
        }
        if (placeholder) {
            placeholder.textContent = 'Select a region to load Wikipedia.';
            placeholder.style.display = 'block';
        }
        if (fallback) fallback.style.display = 'none';
    }

    updateCastDebugOverlay(castPayload) {
        let el = document.getElementById('cast-debug');
        if (!el) {
            el = document.createElement('div');
            el.id = 'cast-debug';
            document.body.appendChild(el);
        }

        if (!castPayload || this.activeTab !== 'predictions') {
            el.style.display = 'none';
            return;
        }

        const rows = Array.isArray(castPayload.rows) ? castPayload.rows : [];
        const listHtml = rows.length > 0
            ? rows.map((r) => `<div>${r.admin1} <span class="cast-debug-count">${Math.round(Number(r.total) || 0)}</span></div>`).join('')
            : '<div>No admin1 rows</div>';

        el.innerHTML = `
            <div class="cast-debug-title">CAST Debug • ${castPayload.label || 'Unknown'}</div>
            <div class="cast-debug-body">${listHtml}</div>
        `;
        el.style.display = 'block';
    }

    hidePanel() {
        const panel = this.$('details-panel');
        if (panel) panel.classList.remove('open');
        document.body.classList.remove('panel-open');
        this._resetWikiTab?.();
        setTimeout(() => window.dispatchEvent(new Event('resize')), 350);
    }

    /* ----------------------------------------------------------------
       COUNTRY / REGION PANEL (The "White" Panel)
       Triggered by Map Clicks on Regions
    ---------------------------------------------------------------- */
    showPanel(name, code, level, info, volatile, currencyRates, opts = {}) {
        const panel = this.$('details-panel');
        if (!panel) return;

        this._panelRequestId = (this._panelRequestId || 0) + 1;
        const requestId = this._panelRequestId;

        panel.classList.add('open');
        document.body.classList.add('panel-open');
        this._resetWikiTab?.();

        // Title & Description
        this.$('panel-title').textContent = name || 'Unknown Region';
        this.$('panel-subtitle').textContent = (level === 0) ? 'Country' : (level === 1 ? 'State/Province' : 'District/Region');
        const descWrap = this.$('panel-description-wrap');
        if (descWrap) descWrap.style.display = 'none';

        this._currentWikiTitle = null;
        this._currentWikiUrl = null;
        const apiBase = 'http://localhost:8000';
        const countryIso = opts?.countryIso ?? (level === 0 ? code : null);
        if (name) {
            const params = new URLSearchParams({ place: name });
            if (countryIso) params.set('iso', countryIso);
            fetch(`${apiBase}/api/wikipedia/lookup?${params}`)
                .then(r => r.json())
                .then(data => {
                    if (requestId !== this._panelRequestId) return;
                    if (data.error) return;
                    this._currentWikiTitle = data.title;
                    this._currentWikiUrl = data.url;
                    this._maybeLoadWikiIframe();
                })
                .catch(() => {
                    if (requestId !== this._panelRequestId) return;
                });
        }

        // --- PREDICTIONS LOGIC (ASYNC LIVE PULL) ---
        const predTab = this.$('tab-btn-predictions');
        const predContainer = this.$('predictions-container');

        // Show tab immediately, show loader inside
        if (predTab) {
            predTab.style.display = 'block';
            // Note: Ideally we check if we *can* fetch, but for now we try for all
        }

        if (predContainer) {
            predContainer.innerHTML = `<div class="p-4 text-xs text-gray-500 animate-pulse">Contacting Server... Fetching ACLED CAST Data for ${name}...</div>`;

            if (window.app && window.app.dataManager) {
                // Determine Admin1 logic if level > 0? 
                // For now, simple country fetch
                window.app.dataManager.getCastForecast(name)
                    .then(forecasts => {
                        if (requestId !== this._panelRequestId) return;
                        if (forecasts && forecasts.length > 0) {
                            this.renderPredictions(forecasts, name);
                        } else {
                            predContainer.innerHTML = `<div class="p-4 text-xs text-gray-500">No forecast data returned (or connection failed).</div>`;
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        if (requestId !== this._panelRequestId) return;
                        predContainer.innerHTML = `<div class="p-4 text-xs text-red-400">Error fetching forecast. Server might be offline.</div>`;
                    });
            }
        }
        // -------------------------

        // Quick Facts
        const quickFacts = this.$('section-quick-facts');
        if (info) {
            quickFacts.style.display = 'block';
            this.$('data-capital').textContent = info.capital || '—';
            this.$('data-continent').textContent = info.continent || '—';

            let currencyText = '—';
            if (info.currency) {
                currencyText = `${info.currency.symbol || ''} ${info.currency.name}`;
                if (currencyRates.rates && info.currency.code) {
                    const rate = currencyRates.rates[info.currency.code];
                    if (rate) {
                        currencyText += ` (1 ${info.currency.code} ≈ ₹${rate.toFixed(2)})`;
                    }
                }
            }
            this.$('data-currency').textContent = currencyText;
        } else {
            quickFacts.style.display = 'none';
        }

        // Languages
        const langSection = this.$('section-languages');
        const langTags = this.$('language-tags');
        if (info && info.languages && info.languages.length > 0) {
            langSection.style.display = 'block';
            langTags.innerHTML = info.languages
                .map(lang => `<span class="tag">${lang}</span>`)
                .join('');
        } else {
            langSection.style.display = 'none';
            langTags.innerHTML = '';
        }

        // Religions (Stacked Bar)
        this.renderReligions(info);

        // Symbols
        const symbolsSection = this.$('section-symbols-tab');
        if (info && (info.national_animal || info.national_bird || info.national_flower)) {
            symbolsSection.style.display = 'block';
            this.$('symbol-animal').textContent = info.national_animal || '—';
            this.$('symbol-bird').textContent = info.national_bird || '—';
            this.$('symbol-flower').textContent = info.national_flower || '—';
        } else {
            symbolsSection.style.display = 'none';
        }

        // Trivia
        const triviaSection = this.$('section-trivia-tab');
        if (info && (info.calling_code || info.tld || info.driving_side)) {
            triviaSection.style.display = 'block';
            this.$('trivia-calling').textContent = info.calling_code || '—';
            this.$('trivia-tld').textContent = info.tld || '—';
            this.$('trivia-driving').textContent = info.driving_side ?
                (info.driving_side === 'left' ? 'Left' : 'Right') : '—';
        } else {
            triviaSection.style.display = 'none';
        }

        // Leaders
        const leadersSection = this.$('section-leaders-tab');
        const leadersContainer = this.$('leaders-container');
        const leadersTabBtn = this.$('tab-btn-leaders');

        if (volatile && volatile.leaders) {
            leadersSection.style.display = 'block';
            if (leadersTabBtn) leadersTabBtn.style.display = 'block';

            const l = volatile.leaders;
            // ... (HTML generation) ...
            let html = '';
            if (l.head_of_state) {
                html += `<div class="leader-card"><div class="leader-title">${l.title_hos || 'Head of State'}</div><div class="leader-name">${l.head_of_state}</div></div>`;
            }
            if (l.head_of_government && l.head_of_government !== l.head_of_state) {
                html += `<div class="leader-card"><div class="leader-title">${l.title_hog || 'Head of Government'}</div><div class="leader-name">${l.head_of_government}</div></div>`;
            }
            leadersContainer.innerHTML = html;
        } else {
            leadersSection.style.display = 'none';
            leadersContainer.innerHTML = '';
            if (leadersTabBtn) leadersTabBtn.style.display = 'none';
        }

        // Economy
        const economySection = this.$('section-economy-tab');
        if (volatile && (volatile.population || volatile.gdp_usd)) {
            economySection.style.display = 'block';
            this.$('data-population').textContent = volatile.population_formatted || '—';
            this.$('data-gdp').textContent = volatile.gdp_formatted || '—';
            this.$('data-gdp-pc').textContent = volatile.gdp_per_capita_formatted || '—';
            this.$('data-area').textContent = volatile.area_formatted || '—';
        } else {
            economySection.style.display = 'none';
        }

        // Hide claimants (interactions specific)
        this.$('section-claimants').style.display = 'none';

        // Reset to Info tab
        this.switchTab('info');
        window.dispatchEvent(new Event('resize'));
    }

    renderReligions(info) {
        const religionSection = this.$('section-religions');
        const religionBar = this.$('religion-bar');
        const religionLegend = this.$('religion-legend');

        if (info && info.religions) {
            religionSection.style.display = 'block';
            const entries = Object.entries(info.religions).sort((a, b) => b[1] - a[1]);

            // Build stacked bar segments
            religionBar.innerHTML = entries.map(([religion, percent]) => {
                const bgColor = this.RELIGION_COLORS[religion] || this.RELIGION_COLORS['Other'];
                const label = percent >= 10 ? `${Math.round(percent)}%` : '';
                return `<div class="religion-segment" style="width: ${percent}%; background: ${bgColor};">${label}</div>`;
            }).join('');

            // Build legend
            religionLegend.innerHTML = entries.map(([religion, percent]) => {
                const bgColor = this.RELIGION_COLORS[religion] || this.RELIGION_COLORS['Other'];
                return `<div class="religion-legend-item">
                    <div class="religion-legend-dot" style="background: ${bgColor};"></div>
                    <span>${religion} ${percent}%</span>
                </div>`;
            }).join('');
        } else {
            religionSection.style.display = 'none';
            religionBar.innerHTML = '';
            religionLegend.innerHTML = '';
        }
    }

    renderPredictions(forecasts, regionName, options = {}) {
        const container = this.$('predictions-container');
        if (!container) return;
        if (!Array.isArray(forecasts) || forecasts.length === 0) {
            container.innerHTML = `<div class="panel-placeholder">No forecast data returned.</div>`;
            return;
        }

        const toNumber = (value) => {
            const n = Number(value);
            return Number.isFinite(n) ? n : 0;
        };

        const formatNumber = (value) => {
            const rounded = Math.round(toNumber(value));
            return rounded.toLocaleString();
        };

        const escapeHtml = (value) => {
            const str = String(value ?? '');
            return str.replace(/[&<>"']/g, (char) => {
                const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
                return map[char] || char;
            });
        };

        const now = new Date();
        const currentYear = now.getFullYear();
        const currentMonth = now.getMonth() + 1;
        const monthNames = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ];

        const parseYear = (value) => {
            const n = Number(value);
            return Number.isFinite(n) && n > 1900 ? n : null;
        };

        const parseMonth = (value) => {
            if (value === null || value === undefined) return null;
            if (typeof value === 'number') {
                return value >= 1 && value <= 12 ? value : null;
            }
            if (typeof value === 'string') {
                const trimmed = value.trim();
                if (!trimmed) return null;
                const asNum = Number(trimmed);
                if (Number.isFinite(asNum) && asNum >= 1 && asNum <= 12) return asNum;
                const lower = trimmed.toLowerCase();
                const monthLookup = {
                    january: 1, jan: 1,
                    february: 2, feb: 2,
                    march: 3, mar: 3,
                    april: 4, apr: 4,
                    may: 5,
                    june: 6, jun: 6,
                    july: 7, jul: 7,
                    august: 8, aug: 8,
                    september: 9, sept: 9, sep: 9,
                    october: 10, oct: 10,
                    november: 11, nov: 11,
                    december: 12, dec: 12
                };
                return monthLookup[lower] || null;
            }
            return null;
        };

        // Group rows by year+month so we can show a timeline and allow month selection.
        const yearMonthMap = new Map(); // year -> monthNum -> rows
        const yearSet = new Set();

        forecasts.forEach((f) => {
            const y = parseYear(f.year);
            const m = parseMonth(f.month);
            if (y === null || m === null) return;
            yearSet.add(y);

            if (!yearMonthMap.has(y)) yearMonthMap.set(y, new Map());
            const monthMap = yearMonthMap.get(y);
            if (!monthMap.has(m)) monthMap.set(m, []);
            monthMap.get(m).push(f);
        });

        const availableYears = Array.from(yearSet.values()).sort((a, b) => a - b);
        const fallbackYear = availableYears.length > 0 ? availableYears[availableYears.length - 1] : currentYear;
        const requestedYear = parseYear(options.year);

        let yearValue = requestedYear && yearMonthMap.has(requestedYear) ? requestedYear : null;
        if (yearValue === null) {
            yearValue = yearMonthMap.has(currentYear) ? currentYear : fallbackYear;
        }

        const monthMap = yearMonthMap.get(yearValue) || new Map();
        const monthNums = Array.from(monthMap.keys()).sort((a, b) => a - b);

        const requestedMonth = parseMonth(options.month);
        let monthValue = requestedMonth && monthMap.has(requestedMonth) ? requestedMonth : null;
        if (monthValue === null) {
            if (yearValue === currentYear && monthMap.has(currentMonth)) {
                monthValue = currentMonth;
            } else if (yearValue === currentYear) {
                const next = monthNums.find(m => m > currentMonth);
                monthValue = next || monthNums[monthNums.length - 1] || null;
            } else {
                monthValue = monthNums[monthNums.length - 1] || null;
            }
        }

        // If we failed to parse/group (unexpected API shape), fall back to the first row display.
        if (monthValue === null) {
            monthValue = parseMonth(forecasts[0]?.month) || currentMonth;
        }

        const scopedForecasts = monthMap.get(monthValue) || forecasts;
        const monthLabel = monthNames[monthValue - 1] || 'Upcoming';

        let totalPred = 0;
        let battles = 0;
        let erv = 0;
        let violence = 0;
        let timestamp = null;

        const admin1Map = new Map();

        scopedForecasts.forEach((f) => {
            const total = toNumber(f.total_forecast);
            const battlesVal = toNumber(f.battles_forecast);
            const ervVal = toNumber(f.erv_forecast);
            const violenceVal = toNumber(f.vac_forecast);
            totalPred += total;
            battles += battlesVal;
            erv += ervVal;
            violence += violenceVal;

            const admin1 = f.admin1 || 'Unknown';
            const current = admin1Map.get(admin1) || { admin1, total: 0, battles: 0, erv: 0, violence: 0 };
            current.total += total;
            current.battles += battlesVal;
            current.erv += ervVal;
            current.violence += violenceVal;
            admin1Map.set(admin1, current);

            if (timestamp === null && f.timestamp) {
                const ts = toNumber(f.timestamp);
                if (ts > 0) timestamp = ts;
            }
        });

        const other = Math.max(totalPred - (battles + erv + violence), 0);
        const safeTotal = totalPred > 0 ? totalPred : 1;

        const percentBattles = Math.round((battles / safeTotal) * 100);
        const percentErv = Math.round((erv / safeTotal) * 100);
        const percentViolence = Math.round((violence / safeTotal) * 100);
        const percentOther = Math.max(0, 100 - percentBattles - percentErv - percentViolence);

        const hotspots = Array.from(admin1Map.values())
            .sort((a, b) => b.total - a.total)
            .slice(0, 6);

        const maxHotspot = Math.max(1, ...hotspots.map(h => h.total));

        // Month timeline (aggregated totals per month for selected year)
        const monthlyTotals = monthNums.map((m) => {
            const rows = monthMap.get(m) || [];
            let t = 0, b = 0, e = 0, v = 0;
            rows.forEach((r) => {
                t += toNumber(r.total_forecast);
                b += toNumber(r.battles_forecast);
                e += toNumber(r.erv_forecast);
                v += toNumber(r.vac_forecast);
            });
            const o = Math.max(t - (b + e + v), 0);
            return { month: m, total: t, battles: b, erv: e, violence: v, other: o };
        });

        const maxMonthlyTotal = Math.max(1, ...monthlyTotals.map(x => x.total));
        const chartW = 320;
        const chartH = 48;
        const pad = 4;
        const bars = monthlyTotals.length || 1;
        const gap = 6;
        const barW = Math.max(10, Math.floor((chartW - pad * 2 - gap * (bars - 1)) / bars));
        const labelY = chartH + 10;

        const svgRects = monthlyTotals.map((x, idx) => {
            const x0 = pad + idx * (barW + gap);
            const scale = (val) => Math.round((toNumber(val) / maxMonthlyTotal) * (chartH - pad * 2));
            const hBattles = scale(x.battles);
            const hErv = scale(x.erv);
            const hViolence = scale(x.violence);
            const hOther = scale(x.other);

            let y = chartH - pad;
            const parts = [];
            const add = (h, cls) => {
                if (h <= 0) return;
                y -= h;
                parts.push(`<rect x="${x0}" y="${y}" width="${barW}" height="${h}" class="${cls}"></rect>`);
            };
            add(hOther, 'cast-svg-other');
            add(hViolence, 'cast-svg-violence');
            add(hErv, 'cast-svg-erv');
            add(hBattles, 'cast-svg-battles');

            const label = monthNames[x.month - 1]?.slice(0, 3) || '';
            const labelX = x0 + Math.floor(barW / 2);
            return `
                <g class="cast-svg-bar ${x.month === monthValue ? 'active' : ''}" data-month="${x.month}">
                    ${parts.join('')}
                    <text x="${labelX}" y="${labelY}" text-anchor="middle" class="cast-svg-label">${escapeHtml(label)}</text>
                </g>
            `;
        }).join('');

        const updatedLabel = timestamp ? new Date(timestamp * 1000).toLocaleString() : null;
        const castLabel = `${monthLabel} ${yearValue}`;

        const castRows = hotspots.map((row) => ({
            admin1: row.admin1,
            total: row.total,
            battles: row.battles,
            erv: row.erv,
            violence: row.violence
        }));

        this.latestCast = {
            label: castLabel,
            month: monthValue,
            year: yearValue,
            rows: castRows
        };

        window.dispatchEvent(new CustomEvent('cast-data-update', {
            detail: this.latestCast
        }));

        this.updateCastDebugOverlay(this.latestCast);

        container.innerHTML = `
            <div class="cast-wrap">
                <div class="cast-card">
                    <div class="cast-header">
                        <div>
                            <div class="cast-title">
                                <div>ACLED: Armed Conflict Location &amp; Event Data</div>
                                <div>CAST: Conflict Alert and Scenario Tracking</div>
                            </div>
                            <a class="cast-link" href="https://acleddata.com/platform/cast-conflict-alert-system" target="_blank" rel="noopener">ACLED CAST website</a>
                            <div class="cast-subtitle">${escapeHtml(monthLabel)} ${escapeHtml(yearValue)} • ${escapeHtml(regionName || 'Selected Country')}</div>
                            <div class="cast-months" role="tablist" aria-label="CAST months">
                                ${monthlyTotals.map((m) => `
                                    <button class="cast-month-btn ${m.month === monthValue ? 'active' : ''}" data-month="${m.month}" data-year="${yearValue}">
                                        ${escapeHtml(monthNames[m.month - 1]?.slice(0, 3) || m.month)}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                        <div class="cast-badges">
                            <span class="cast-badge">High Confidence</span>
                            ${updatedLabel ? `<div class="cast-updated" title="CAST data timestamp">${escapeHtml(updatedLabel)}</div>` : ''}
                        </div>
                    </div>

                    <div class="cast-kpis">
                        <div class="cast-kpi">
                            <div class="cast-kpi-label">Total Predicted</div>
                            <div class="cast-kpi-value">${formatNumber(totalPred)}</div>
                        </div>
                        <div class="cast-kpi">
                            <div class="cast-kpi-label">Battles</div>
                            <div class="cast-kpi-value">${formatNumber(battles)}</div>
                        </div>
                        <div class="cast-kpi">
                            <div class="cast-kpi-label">Explosions / Remote Violence</div>
                            <div class="cast-kpi-value">${formatNumber(erv)}</div>
                        </div>
                        <div class="cast-kpi">
                            <div class="cast-kpi-label">Violence (Civilians)</div>
                            <div class="cast-kpi-value">${formatNumber(violence)}</div>
                        </div>
                    </div>

                    <div class="cast-trend">
                        <div class="cast-mini-title">Forecast Timeline (${escapeHtml(yearValue)})</div>
                        <div class="cast-chart" title="Click a month label to switch">
                            <svg viewBox="0 0 ${chartW} ${chartH + 18}" width="100%" height="72" preserveAspectRatio="none">
                                ${svgRects}
                            </svg>
                        </div>
                        <div class="cast-bar-legend">
                            <span><span class="cast-legend-dot cast-bar-battles"></span> Battles</span>
                            <span><span class="cast-legend-dot cast-bar-erv"></span> ERV</span>
                            <span><span class="cast-legend-dot cast-bar-violence"></span> Violence</span>
                            <span><span class="cast-legend-dot cast-bar-other"></span> Other</span>
                        </div>
                    </div>

                    <div class="cast-mini">
                        <div class="cast-mini-title">Composition</div>
                        <div class="cast-bar">
                            <span class="cast-bar-seg cast-bar-battles" style="width:${percentBattles}%"></span>
                            <span class="cast-bar-seg cast-bar-erv" style="width:${percentErv}%"></span>
                            <span class="cast-bar-seg cast-bar-violence" style="width:${percentViolence}%"></span>
                            <span class="cast-bar-seg cast-bar-other" style="width:${percentOther}%"></span>
                        </div>
                        <div class="cast-bar-legend">
                            <span><span class="cast-legend-dot cast-bar-battles"></span> Battles ${percentBattles}%</span>
                            <span><span class="cast-legend-dot cast-bar-erv"></span> ERV ${percentErv}%</span>
                            <span><span class="cast-legend-dot cast-bar-violence"></span> Violence ${percentViolence}%</span>
                            <span><span class="cast-legend-dot cast-bar-other"></span> Other ${percentOther}%</span>
                        </div>
                    </div>
                </div>

                <div class="cast-section">
                    <div class="cast-section-title">Regional Hotspots (Admin1)</div>
                    <div class="cast-hotspots">
                        ${hotspots.map(h => `
                            <div class="cast-hotspot-row">
                                <div class="cast-hotspot-label">${escapeHtml(h.admin1)}</div>
                                <div class="cast-hotspot-bar">
                                    <span style="width:${Math.round((h.total / maxHotspot) * 100)}%"></span>
                                </div>
                                <div class="cast-hotspot-value">${formatNumber(h.total)}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="cast-footer">Source: ACLED CAST API • Model ${escapeHtml(yearValue)}</div>
            </div>
        `;

        // Month switching
        container.querySelectorAll('.cast-month-btn').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const m = parseMonth(btn.dataset.month);
                const y = parseYear(btn.dataset.year);
                this.renderPredictions(forecasts, regionName, { month: m, year: y });
            });
        });

        // Also allow clicking month labels in the mini chart.
        container.querySelectorAll('.cast-svg-bar').forEach((g) => {
            g.addEventListener('click', () => {
                const m = parseMonth(g.dataset.month);
                this.renderPredictions(forecasts, regionName, { month: m, year: yearValue });
            });
        });
    }

    showDisputePanel(dispute, countryInfoFn) {
        const panel = this.$('details-panel');
        panel.classList.add('open');
        document.body.classList.add('panel-open');
        this.switchTab('info');
        const descWrap = this.$('panel-description-wrap');
        if (descWrap) descWrap.style.display = 'block';

        const regionName = dispute.region || dispute.name || 'Unknown Region';
        this._resetWikiTab?.();
        this._currentWikiTitle = null;
        this._currentWikiUrl = null;
        fetch(`http://localhost:8000/api/wikipedia/lookup?place=${encodeURIComponent(regionName)}`)
            .then(r => r.json())
            .then(data => {
                if (!data.error) {
                    this._currentWikiTitle = data.title;
                    this._currentWikiUrl = data.url;
                    this._maybeLoadWikiIframe?.();
                }
            })
            .catch(() => {});

        if (dispute.toast_message) {
            this.toast(dispute.toast_message, dispute.toast_type || 'info');
        }

        const getInfo = countryInfoFn || ((iso) => ({ name: iso, flag_emoji: '' }));
        const claimants = dispute.claimants || dispute.participants || [];
        const description = dispute.description || dispute.short_description || 'No description available.';
        const dateStr = dispute.since || dispute.date || '—';
        const hasInlineAnalysis = !!dispute.llm_analysis;
        const analysisHtml = hasInlineAnalysis ? this.formatAnalysisHtml(dispute.llm_analysis) : '';

        let sources = [];
        if (dispute.source) sources.push({ url: dispute.source, name: 'Primary Source' });
        if (dispute.sources && Array.isArray(dispute.sources)) {
            dispute.sources.forEach(s => {
                if (typeof s === 'string') sources.push({ url: s, name: 'Source' });
                else if (s && s.url) sources.push({ url: s.url, name: s.type || s.name || 'Source' });
            });
        }

        const flagEmojis = claimants.map(c => getInfo(c)?.flag_emoji || '').join(' ');
        this.$('panel-title').textContent = `${flagEmojis} ${regionName}`;
        this.$('panel-subtitle').textContent = 'Interaction Details';

        const linksHtml = sources.map(s => {
            const safeUrl = this.escapeHtml(s.url);
            return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" style="color: #c2410c; text-decoration: underline; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px;">${safeUrl}</a>`;
        }).join('');
        const sourcesBoxHtml = sources.length > 0 ? `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #fed7aa;">
                <strong>Sources:</strong>
                ${linksHtml}
            </div>
        ` : '';

        const involvedStr = this.escapeHtml(claimants.map(c => getInfo(c)?.name || c).join(', '));
        const descEscaped = this.escapeHtml(description);
        const typeEscaped = this.escapeHtml(dispute.type);
        const statusEscaped = this.escapeHtml(dispute.status);
        const dateEscaped = this.escapeHtml(dateStr);
        this.$('panel-description').innerHTML = `
        <p><strong>Involved:</strong> ${involvedStr}</p>
        <p>${descEscaped}</p>
        ${analysisHtml}
        <div style="margin-top:10px; font-size:0.9em;">
            <div><strong>Type:</strong> ${typeEscaped}</div>
            <div><strong>Status:</strong> ${statusEscaped}</div>
            <div><strong>Date:</strong> ${dateEscaped}</div>
            ${sourcesBoxHtml}
        </div>
        <div id="panel-analysis-loading" style="display:none; margin-top:8px; color:#64748b;">Loading analysis…</div>
        <div id="panel-analysis-block" style="display:none;"></div>
        `;

        if (dispute.id && !hasInlineAnalysis) {
            const loadingEl = this.$('panel-analysis-loading');
            const blockEl = this.$('panel-analysis-block');
            if (loadingEl) loadingEl.style.display = 'block';
            const url = `http://localhost:8000/api/interactions/${encodeURIComponent(dispute.id)}/analysis`;
            fetch(url)
                .then(r => r.json())
                .then(data => {
                    if (loadingEl) loadingEl.style.display = 'none';
                    const text = data.analysis || '';
                    if (blockEl && text) {
                        blockEl.style.display = 'block';
                        blockEl.innerHTML = this.formatAnalysisHtml(text);
                    }
                })
                .catch(() => {
                    if (loadingEl) loadingEl.style.display = 'none';
                });
        }

        // Hide standard sections
        ['section-quick-facts', 'section-languages', 'section-religions',
            'section-symbols-tab', 'section-trivia-tab', 'section-leaders-tab',
            'section-economy-tab'].forEach(id => {
                const el = this.$(id);
                if (el) el.style.display = 'none';
            });

        // Show claimants section
        const claimantsSection = this.$('section-claimants');
        const claimantsList = this.$('claimants-list');
        if (claimantsSection && claimantsList) {
            claimantsSection.style.display = 'block';
            claimantsList.innerHTML = claimants.map(iso => {
                const info = getInfo(iso);
                const label = this.escapeHtml(info?.name || iso);
                return `<span class="tag">${info?.flag_emoji || ''} ${label}</span>`;
            }).join('');
        }

        this.switchTab('info');
        window.dispatchEvent(new Event('resize'));
    }

    updateSidePanel(feature) {
        if (!this.sidePanel) return;

        const props = feature.properties || {};
        const category = props.category || "UNKNOWN";

        // Valid categories: CONFLICT, VIOLENCE, PROTEST, DISASTER, DISPLACEMENT, CRIME, ACCIDENT
        const headerColor = this.getCategoryColor(category);

        this.sidePanel.innerHTML = `
      <div class="flex flex-col h-full bg-gray-900 text-white font-sans">
        <!-- Header -->
        <div class="p-4 border-b border-gray-700" style="background-color: ${headerColor}20; border-left: 4px solid ${headerColor}">
            <div class="flex justify-between items-start">
                <div>
                    <h2 class="text-xl font-bold tracking-tight uppercase" style="color: ${headerColor}">${category}: ${props.name.split(':')[1] || "REGION"}</h2>
                    <div class="text-xs text-gray-400 mt-1">INTERACTION DETAILS</div>
                </div>
                <button id="closePanelBtn" class="text-gray-400 hover:text-white">&times;</button>
            </div>
        </div>

        <!-- Scrollable Content -->
        <div class="flex-1 overflow-y-auto">
            <div class="p-4 space-y-4">
                <div>
                    <h3 class="text-xs font-bold text-gray-500 uppercase mb-1">Involved:</h3>
                    <p class="text-md">${props.name || "Unidentified Group"}</p>
                    <p class="text-sm text-gray-400">Sources: ${props.importance || 0}</p>
                </div>

                <div class="bg-gray-800 p-3 rounded border border-gray-700">
                    <h3 class="font-bold text-sm mb-1 text-gray-300 uppercase">${category}</h3>
                    <p class="text-sm text-gray-400">Actor: ${props.name.split(':')[1] || "Unknown"}</p>
                    <p class="text-sm text-gray-400">Location: ${props.countryname || "Unknown"}</p>
                </div>

                <div class="space-y-1 mt-4">
                    <div class="flex justify-between text-xs text-gray-500 border-b border-gray-800 pb-1">
                        <span>Type:</span> <span class="text-gray-300">${category}</span>
                    </div>
                     <div class="flex justify-between text-xs text-gray-500 border-b border-gray-800 pb-1">
                        <span>Status:</span> <span class="text-green-400">Active (Live)</span>
                    </div>
                    <div class="flex justify-between text-xs text-gray-500 border-b border-gray-800 pb-1">
                        <span>Date:</span> <span class="text-gray-300">${props.date}</span>
                    </div>
                </div>
                
                <div id="sidepanel-wiki-block" class="mt-6 pt-4 border-t border-gray-700">
                    <div id="sidepanel-wiki-loading" class="text-sm text-gray-400">Loading Wikipedia…</div>
                    <div id="sidepanel-wiki-content" style="display:none;"></div>
                    <a href="#" id="wikiBtn" class="text-sm text-blue-400 hover:text-blue-300 underline flex items-center gap-1" style="display:none;">
                        Read on Wikipedia ↗
                    </a>
                </div>
            </div>
        </div>
      </div>
    `;

        document.getElementById("closePanelBtn").onclick = () => this.hideSidePanel();

        const loadingEl = document.getElementById('sidepanel-wiki-loading');
        const contentEl = document.getElementById('sidepanel-wiki-content');
        const wikiBtn = document.getElementById('wikiBtn');
        const placeQuery = props.countryname || props.name?.split(':')[1] || category;
        const coords = feature.geometry?.coordinates;
        const lat = coords && coords.length >= 2 ? coords[1] : null;
        const lon = coords && coords.length >= 2 ? coords[0] : null;
        const params = new URLSearchParams({ place: placeQuery });
        if (lat != null && lon != null) {
            params.set('lat', lat);
            params.set('lon', lon);
        }
        fetch(`http://localhost:8000/api/wikipedia/lookup?${params}`)
            .then(r => r.json())
            .then(data => {
                if (loadingEl) loadingEl.style.display = 'none';
                if (data.error) {
                    if (wikiBtn) {
                        wikiBtn.style.display = 'inline-flex';
                        wikiBtn.href = `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(placeQuery)}`;
                        wikiBtn.onclick = (e) => { e.preventDefault(); window.open(wikiBtn.href, '_blank'); };
                    }
                    return;
                }
                if (contentEl) {
                    const thumb = data.thumbnail ? `<img src="${this.escapeHtml(data.thumbnail)}" alt="" style="max-width:100%; height:auto; border-radius:4px; margin-bottom:8px;">` : '';
                    const extract = (data.extract || '').slice(0, 600) + ((data.extract || '').length > 600 ? '…' : '');
                    const clean = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(`<div class="wiki-embed"><h4 class="text-sm font-bold text-gray-300 mb-2">${this.escapeHtml(data.title)}</h4>${thumb}<p class="text-sm text-gray-300 leading-relaxed">${this.escapeHtml(extract)}</p></div>`) : `<div class="wiki-embed"><h4 class="text-sm font-bold text-gray-300 mb-2">${this.escapeHtml(data.title)}</h4>${thumb}<p class="text-sm text-gray-300 leading-relaxed">${this.escapeHtml(extract)}</p></div>`;
                    contentEl.innerHTML = clean;
                    contentEl.style.display = 'block';
                }
                if (wikiBtn) {
                    wikiBtn.style.display = 'inline-flex';
                    wikiBtn.href = data.url;
                    wikiBtn.textContent = 'Read full article on Wikipedia ↗';
                    wikiBtn.onclick = (e) => { e.preventDefault(); window.open(data.url, '_blank'); };
                }
            })
            .catch(() => {
                if (loadingEl) loadingEl.style.display = 'none';
                if (wikiBtn) {
                    wikiBtn.style.display = 'inline-flex';
                    wikiBtn.href = `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(placeQuery)}`;
                    wikiBtn.onclick = (e) => { e.preventDefault(); window.open(wikiBtn.href, '_blank'); };
                }
            });
    }
}
