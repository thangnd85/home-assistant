class VinFastDigitalTwin extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this._map = null;
    this._polyline = null;
    this._marker = null;
    this._stationLayer = null;
    this._leafletLoaded = false;
    this._lastLat = null;
    this._lastLon = null;
    
    this._lastHeadingLat = null;
    this._lastHeadingLon = null;
    this._currentAngle = undefined; 
    
    this._isReplaying = false;
    this._replayTimer = null;
    this._tripHistory = []; 
    this._selectedRouteCoords = []; 
    this._stationFilter = 'ALL'; 
    this._currentStations = []; 
    this._backendData = {};
    this._powerFetchTimer = null;
    this._currentPolylineString = null;
    this._chargeHistoryData = [];
    
    this._effToggleTimer = null;
    this._effToggleState = false;
  }

  loadLeaflet() {
    if (this._leafletLoaded) return;
    this._leafletLoaded = true;
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => { setTimeout(() => this.initMap(), 200); };
    document.head.appendChild(script);
  }

  async fetchChargeHistory(vin) {
      if (!vin) return;
      try {
          const res = await fetch(`/local/vinfast_charge_history_${vin.toLowerCase()}.json?v=${new Date().getTime()}`);
          if (res.ok) {
              this._chargeHistoryData = await res.json();
              const box = this.querySelector('#box-charge');
              if (box && box.classList.contains('active-box')) {
                  this.renderChargeHistory();
              }
          }
      } catch(e) {}
  }

  async fetchBackendState(vin) {
      if (!vin) return;
      try {
          const res = await fetch(`/local/vinfast_state_${vin.toLowerCase()}.json?v=${new Date().getTime()}`);
          if (res.ok) {
              const stateData = await res.json();
              if (stateData && stateData.last_data) {
                  this._backendData = stateData.last_data;
                  
                  const powerEl = this.querySelector('#vf-charge-power');
                  if (powerEl) {
                      let pwr = this._backendData.api_live_charge_power || 0;
                      powerEl.innerText = pwr > 0 ? `${pwr} kW` : 'Đang tính...';
                  }

                  if (this._backendData.api_charge_history_list && (!this._chargeHistoryData || this._chargeHistoryData.length === 0)) {
                      try { this._chargeHistoryData = JSON.parse(this._backendData.api_charge_history_list); } catch(e){}
                  }

                  if (this._map && this._lastLat === null && this._backendData.api_last_lat) {
                      this._lastLat = parseFloat(this._backendData.api_last_lat);
                      this._lastLon = parseFloat(this._backendData.api_last_lon);
                      this._map.setView([this._lastLat, this._lastLon], 15);
                      if (this._marker) {
                          this._marker.setLatLng([this._lastLat, this._lastLon]);
                          this._marker.setOpacity(1);
                      }
                  }
              }
          }
      } catch(e) {}
  }

  cleanRouteData(points) {
      if (!points || !Array.isArray(points) || points.length === 0) return [];
      return points; 
  }

  async fetchTripHistory(vin) {
    if (!vin) return;
    try {
        const res = await fetch(`/local/vinfast_trips_${vin.toLowerCase()}.json?v=${new Date().getTime()}`);
        if (res.ok) {
            this._tripHistory = await res.json();
            this.renderTripSelector();
        }
    } catch(e) {}
  }

  renderEmptyTripSelector() {
      const selectEl = this.querySelector('#trip-selector');
      if (selectEl) selectEl.innerHTML = `<option value="current">📍 Đang ghi Trip...</option>`;
  }

  renderTripSelector() {
      const selectEl = this.querySelector('#trip-selector');
      if (!selectEl || this._tripHistory.length === 0) {
          this.renderEmptyTripSelector();
          return;
      }
      let options = `<option value="current">📍 Chuyến đi hiện tại</option>`;
      this._tripHistory.forEach((trip, index) => {
          let shortStart = (trip.start_address || "").split(',')[0].substring(0, 15);
          options += `<option value="${index}">🗓 ${trip.date} ${trip.start_time} - ${trip.distance}km (${shortStart}...)</option>`;
      });
      selectEl.innerHTML = options;
  }

  getBearing(startLat, startLng, destLat, destLng) {
      startLat = startLat * Math.PI / 180; startLng = startLng * Math.PI / 180;
      destLat = destLat * Math.PI / 180; destLng = destLng * Math.PI / 180;
      const y = Math.sin(destLng - startLng) * Math.cos(destLat);
      const x = Math.cos(startLat) * Math.sin(destLat) - Math.sin(startLat) * Math.cos(destLat) * Math.cos(destLng - startLng);
      let brng = Math.atan2(y, x);
      return (brng * 180 / Math.PI + 360) % 360;
  }

  _smoothRotation(targetAngle) {
      if (this._currentAngle === undefined) {
          this._currentAngle = targetAngle;
          return targetAngle;
      }
      let diff = targetAngle - (this._currentAngle % 360);
      diff = ((diff + 540) % 360) - 180;
      this._currentAngle += diff;
      return this._currentAngle;
  }

  getCarIcon(angle = 0, speed = null) {
      if(typeof L === 'undefined') return null;
      const arrowSvg = `<svg class="car-dir-svg" viewBox="0 0 24 24" fill="#2563eb" stroke="white" stroke-width="2" style="position: absolute; top: 0; left: 0; transform: rotate(${angle}deg); transform-origin: center; transition: transform 0.3s ease-out; width: 28px; height: 28px; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); z-index: 1000;"><path d="M12 2L22 20L12 17L2 20L12 2Z"/></svg>`;
      let speedDisplay = speed !== null ? 'block' : 'none';
      let speedVal = speed !== null ? speed : 0;
      const speedBadge = `<div class="car-speed-badge" style="position: absolute; bottom: 32px; left: 50%; transform: translateX(-50%); background: #10b981; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; border: 1px solid white; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.3); z-index: 1001; display: ${speedDisplay}; transition: all 0.2s;">${speedVal} km/h</div>`;
      return L.divIcon({ className: '', html: `<div style="position: relative; width: 28px; height: 28px;">${arrowSvg}${speedBadge}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] });
  }

  checkAndShowSmartSuggestion(soc, heading) {
      const suggestCard = this.querySelector('#vf-smart-suggestion');
      if (!suggestCard || !this._currentStations || this._currentStations.length === 0) return;
      if (soc > 30 || heading === null) { suggestCard.style.display = 'none'; return; }
      let bestStation = null;
      for (let st of this._currentStations) {
          if (st.avail > 0 && st.dist < 20) {
              let stationBearing = this.getBearing(this._lastLat, this._lastLon, st.lat, st.lng);
              let diff = Math.abs(stationBearing - heading);
              if (diff > 180) diff = 360 - diff;
              if (diff < 45 || st.dist < 3.0) {
                  if (!bestStation || st.dist < bestStation.dist) bestStation = st;
              }
          }
      }
      if (bestStation) {
          this.querySelector('#vf-suggest-name').innerText = bestStation.name;
          this.querySelector('#vf-suggest-dist').innerText = bestStation.dist;
          this.querySelector('#vf-suggest-power').innerText = bestStation.power;
          this.querySelector('#vf-suggest-avail').innerText = `${bestStation.avail}/${bestStation.total}`;
          
          const mapDomain = 'https://' + 'www.google.com' + '/maps/dir/?api=1';
          const navUrl = mapDomain + '&origin=' + this._lastLat + ',' + this._lastLon + '&destination=' + bestStation.lat + ',' + bestStation.lng + '&travelmode=driving';
          
          const btnNav = this.querySelector('#btn-suggest-nav');
          if (btnNav) btnNav.onclick = () => window.open(navUrl, '_blank');
          
          suggestCard.style.display = 'block';
      } else {
          suggestCard.style.display = 'none';
      }
  }

  renderStations() {
      if (!this._stationLayer || !this._map || typeof L === 'undefined') return;
      this._stationLayer.clearLayers();
      if (!Array.isArray(this._currentStations)) return;

      this._currentStations.forEach(st => {
          if (st.dist > 5.0) return; 
          const isDC = st.power >= 20;
          if (this._stationFilter === 'DC' && !isDC) return;
          if (this._stationFilter === 'AC' && isDC) return;

          if (st.lat && st.lng) {
              let ratio = st.total > 0 ? (st.avail / st.total) * 100 : 0;
              let pinColor = '', statusText = '';
              if (st.total === 0 || st.avail === 0) { pinColor = '#dc2626'; statusText = 'Hết chỗ'; }
              else if (ratio < 30) { pinColor = '#f97316'; statusText = 'Sắp kín'; }
              else if (ratio < 50) { pinColor = '#eab308'; statusText = 'Đông'; }
              else if (ratio < 80) { pinColor = '#0ea5e9'; statusText = 'Trống'; }
              else { pinColor = '#16a34a'; statusText = 'Vắng'; }

              let boltCount = st.power >= 120 ? 3 : (st.power >= 20 ? 2 : 1);
              let boltsHtml = Array(boltCount).fill(`<ha-icon icon="mdi:flash" style="--mdc-icon-size: 16px; margin: 0 -2px;"></ha-icon>`).join('');
              const pinWidth = boltCount === 1 ? 30 : (boltCount === 2 ? 42 : 54);

              const stationIcon = L.divIcon({ 
                  className: 'custom-station-marker', 
                  html: `<div style="background-color: ${pinColor}; border: 2px solid white; border-radius: 14px; padding: 2px; display: flex; align-items: center; justify-content: center; color: white; box-shadow: 0 3px 6px rgba(0,0,0,0.3); height: 26px; width: ${pinWidth}px;">${boltsHtml}</div>`, 
                  iconSize: [pinWidth, 26], iconAnchor: [pinWidth / 2, 13] 
              });

              const mapDomain = 'https://' + 'www.google.com' + '/maps/dir/?api=1';
              let originParam = (this._lastLat && this._lastLon) ? '&origin=' + this._lastLat + ',' + this._lastLon : '';
              const navUrl = mapDomain + originParam + '&destination=' + st.lat + ',' + st.lng + '&travelmode=driving';

              const popupContent = `
                  <div style="font-family:sans-serif; min-width: 170px;">
                      <b style="font-size: 13px; color: #1e3a8a;">${st.name}</b><br>
                      <div style="margin-top: 6px; font-size: 12px;">
                          🚗 Cách xe: <b>${st.dist} km</b><br>
                          ⚡ Công suất: <b>${st.power} kW</b><br>
                          🔌 Trụ trống: <b style="color:${pinColor}; font-size:14px;">${st.avail} / ${st.total}</b>
                      </div>
                      <a href="${navUrl}" target="_blank" style="display: flex; align-items: center; justify-content: center; gap: 4px; margin-top: 10px; background: #2563eb; color: white; padding: 8px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 12px; transition: background 0.2s;">
                          <svg style="width:16px;height:16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>
                          Chỉ đường
                      </a>
                  </div>
              `;

              L.marker([st.lat, st.lng], {icon: stationIcon}).bindPopup(popupContent).addTo(this._stationLayer);
          }
      });
  }

  initMap() {
    const mapEl = this.querySelector('#vf-map-canvas');
    if (!mapEl || typeof L === 'undefined' || this._map) return;
    
    this._map = L.map(mapEl, { zoomControl: false });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', { maxZoom: 19 }).addTo(this._map);
    this._marker = L.marker([0, 0], {icon: this.getCarIcon(0, null), opacity: 0}).addTo(this._map);
    this._polyline = L.polyline([], {color: '#2563eb', weight: 4, opacity: 0.8}).addTo(this._map);
    this._stationLayer = L.layerGroup().addTo(this._map);
    
    const p = this.config?.entity_prefix || 'vinfast_xe';
    const vinStr = p.includes('_') ? p.split('_')[1] : p;
    this.fetchBackendState(vinStr);

    new IntersectionObserver((entries) => { 
        if (entries[0].isIntersecting && this._map) setTimeout(() => this._map.invalidateSize(), 100); 
    }).observe(mapEl);
  }

  set hass(hass) {
    try {
      this._hass = hass;
      const p = this.config?.entity_prefix || 'vinfast_xe';
      const vinStr = p.includes('_') ? p.split('_')[1] : p;
      
      const getValidState = (entityId) => {
        const stateObj = hass.states[entityId];
        if (!stateObj || stateObj.state === 'unavailable' || stateObj.state === 'unknown' || stateObj.state === '') return null;
        return stateObj.state;
      };

      const formatTimeSince = (dateString) => {
          if (!dateString) return "";
          const s = Math.floor((new Date() - new Date(dateString)) / 1000);
          if (s < 60) return "vừa xong";
          const m = Math.floor(s / 60); if (m < 60) return `${m} phút trước`;
          const h = Math.floor(m / 60); if (h < 24) return `${h} giờ trước`;
          return `${Math.floor(h / 24)} ngày trước`;
      };

      if (!this.content) {
        this.loadLeaflet();
        this.fetchTripHistory(vinStr);
        this.fetchChargeHistory(vinStr); 
        
        this.innerHTML = `
          <ha-card class="vf-card">
            <div class="vf-card-container">
              <div class="vf-header">
                <div class="vf-title">
                  <svg viewBox="0 0 512 512" fill="currentColor"><path d="M560 3586 c-132 -28 -185 -75 -359 -321 -208 -291 -201 -268 -201 -701 0 -361 3 -383 69 -470 58 -77 133 -109 311 -134 202 -29 185 -21 199 -84 14 -62 66 -155 119 -209 110 -113 277 -165 430 -133 141 29 269 125 328 246 l29 59 1115 0 1115 0 29 -59 c60 -123 201 -226 345 -250 253 -43 499 137 543 397 34 203 -77 409 -268 500 -69 33 -89 38 -172 41 -116 5 -198 -15 -280 -67 -116 -76 -195 -193 -214 -321 -6 -36 -12 -71 -14 -77 -5 -19 -2163 -19 -2168 0 -2 6 -8 41 -14 77 -19 128 -98 245 -214 321 -82 52 -164 72 -280 67 -82 -3 -103 -8 -168 -40 -41 -19 -94 -52 -117 -72 -55 -48 -115 -139 -137 -209 -21 -68 -13 -66 -196 -37 -69 11 -128 20 -132 20 -17 0 -82 67 -94 97 -10 23 -14 86 -14 228 l0 195 60 0 c48 0 63 4 80 22 24 26 58 10 88 -12 22 -61 40 -111 40 l-39 0 0 43 c1 23 9 65 18 93 20 58 264 406 317 453 43 37 120 61 198 61 52 0 58 -2 53 -17 -4 -10 -48 -89 -98 -177 -70 -122 -92 -170 -95 -205 -5 -56 19 -106 67 -138 l33 -23 1511 0 c867 0 1583 -4 1680 -10 308 -18 581 -60 788 -121 109 -32 268 -103 268 -119 0 -6 -27 -10 -60 -10 -68 0 -100 -21 -100 -66 0 -63 40 -84 161 -84 l79 0 0 -214 c0 -200 -1 -215 -20 -239 -13 -16 -35 -29 -58 -33 -88 -16 -113 -102 -41 -140 81 -41 228 49 259 160 8 29 11 119 8 292 l-3 249 -32 67 c-45 96 -101 152 -197 197 -235 112 -604 187 -1027 209 l-156 9 -319 203 c-176 112 -359 223 -409 246 -116 56 -239 91 -366 104 -149 15 -1977 12 -2049 -4z m800 -341 l0 -205 -335 0 -336 0 12 23 c7 12 59 104 116 205 l105 182 219 0 219 0 0 -205z m842 15 c14 -102 27 -193 27 -202 1 -17 -23 -18 -359 -18 l-360 0 0 198 c0 109 3 202 7 205 4 4 153 6 332 5 l326 -3 27 -185z m528 157 c52 -14 125 -38 161 -55 54 -24 351 -206 489 -299 l35 -23 -516 0 -516 0 -26 188 c-15 103 -27 196 -27 206 0 18 7 19 153 13 112 -5 177 -12 247 -30z m-1541 -1132 c115 -63 176 -174 169 -305 -16 -272 -334 -402 -541 -221 -20 18 -51 63 -69 99 -28 57 -33 77 -33 142 0 65 5 85 33 142 37 76 93 128 169 159 75 30 200 23 272 -16z m3091 16 c110 -42 192 -149 207 -269 18 -159 -101 -319 -264 -352 -134 -28 -285 47 -350 174 -37 72 -43 180 -14 257 35 91 107 162 200 195 55 20 162 17 221 -5z"></path></svg>
                  <span id="vf-name"></span>
                </div>
                <div class="vf-odo"><div class="vf-odo-label">ODOMETER</div><div class="vf-odo-value"><span id="vf-odo-int"></span> <span class="vf-odo-unit">km</span></div></div>
              </div>

              <div class="vf-car-stage" id="vf-car-stage">
                <div id="vf-status-badge" class="vf-status-badge"></div>
                <img id="vf-car-img" src="" alt="VinFast Car" onerror="this.src='https://shop.vinfastauto.com/on/demandware.static/-/Sites-app_vinfast_vn-Library/default/dw15d3dc68/images/PDP/vf9/M/M.png'">
                <div class="vf-tire vf-tire-fl" id="tire-fl" style="display:none;"><ha-icon icon="mdi:tire"></ha-icon><br><span></span> <span class="tire-unit">bar</span></div>
                <div class="vf-tire vf-tire-fr" id="tire-fr" style="display:none;"><ha-icon icon="mdi:tire"></ha-icon><br><span></span> <span class="tire-unit">bar</span></div>
                <div class="vf-tire vf-tire-rl" id="tire-rl" style="display:none;"><ha-icon icon="mdi:tire"></ha-icon><br><span></span> <span class="tire-unit">bar</span></div>
                <div class="vf-tire vf-tire-rr" id="tire-rr" style="display:none;"><ha-icon icon="mdi:tire"></ha-icon><br><span></span> <span class="tire-unit">bar</span></div>
              </div>

              <div class="vf-controls-area">
                <div class="vf-gears"><span class="gear" id="gear-P">P</span><span class="gear" id="gear-R">R</span><span class="gear" id="gear-N">N</span><span class="gear" id="gear-D">D</span></div>
                <div class="vf-speed" id="vf-speed-container"><span id="vf-speed"></span><span class="vf-speed-unit">km/h</span></div>
              </div>
              
              <div class="vf-doors-status" id="vf-doors-container"></div>
              
              <div class="vf-charging-banner" id="vf-charging-banner" style="display: none;">
                  <div class="charging-left">
                      <div class="charging-title"><ha-icon icon="mdi:ev-plug-type2"></ha-icon><span id="vf-charge-status-text">Hệ thống đang sạc</span></div>
                      <div class="charging-details">Giới hạn: <span id="vf-charge-limit" style="font-weight:bold; margin-left:4px;">--%</span><span style="margin:0 8px;opacity:0.5;">|</span>Công suất: <span id="vf-charge-power" style="font-weight:bold; margin-left:4px;">-- kW</span></div>
                  </div>
                  <div class="charging-right">
                      <span id="vf-charge-time" class="charging-time">--</span>
                      <div class="charging-time-label"><span>phút</span><span>còn lại</span></div>
                  </div>
              </div>

              <div class="vf-remote-bar" id="vf-remote-controls" style="display: none;">
                  <div class="remote-btn" id="btn-rc-lock" title="Khóa cửa"><ha-icon icon="mdi:lock"></ha-icon></div>
                  <div class="remote-btn" id="btn-rc-unlock" title="Mở cửa"><ha-icon icon="mdi:lock-open"></ha-icon></div>
                  <div class="remote-btn" id="btn-rc-horn" title="Bấm còi"><ha-icon icon="mdi:bullhorn"></ha-icon></div>
                  <div class="remote-btn" id="btn-rc-lights" title="Nháy đèn"><ha-icon icon="mdi:car-light-high"></ha-icon></div>
              </div>

              <div class="vf-stats-grid">
                
                <div class="stat-box clickable" id="box-batt">
                  <div class="box-main">
                    <ha-icon icon="mdi:battery-charging-60" style="color: #10b981;"></ha-icon>
                    <div class="stat-info"><div class="stat-label">MỨC PIN</div><div class="stat-val" id="vf-stat-batt">--</div></div>
                  </div>
                </div>
                <div class="stat-box clickable" id="box-range">
                  <div class="box-main">
                    <ha-icon icon="mdi:map-marker-distance" style="color: #3b82f6;"></ha-icon>
                    <div class="stat-info"><div class="stat-label">PHẠM VI</div><div class="stat-val" id="vf-stat-range">--</div></div>
                  </div>
                </div>

                <div class="stat-detail-container" id="detail-container-1">
                    <div class="stat-detail-content" id="detail-batt">
                        <div class="detail-row"><span>Sức khỏe Pin (SOH):</span> <b id="dt-soh" style="color:#10b981;">--</b></div>
                        <div class="detail-row"><span>Lần sạc cuối (Cắm ➔ Rút):</span> <b id="dt-charge-soc">--</b></div>
                    </div>
                    <div class="stat-detail-content" id="detail-range">
                        <div class="detail-row"><span>Thiết kế (NSX):</span> <b id="dt-range-max">--</b></div>
                        <div class="detail-row"><span>Thực tế (Đầy 100%):</span> <b id="dt-range-ai" style="color:#3b82f6;">--</b></div>
                        <div class="detail-row"><span>Tỷ lệ hao hụt dự kiến:</span> <b id="dt-range-drop" style="color:#ef4444;">--</b></div>
                    </div>
                </div>

                <div class="stat-box clickable" id="box-eff">
                  <div class="box-main">
                    <ha-icon icon="mdi:leaf" style="color: #10b981;"></ha-icon>
                    <div class="stat-info"><div class="stat-label" id="lbl-eff">HIỆU SUẤT TB</div><div class="stat-val" id="vf-stat-eff">--</div></div>
                  </div>
                </div>
                <div class="stat-box clickable" id="box-speed">
                  <div class="box-main">
                    <ha-icon icon="mdi:chart-bell-curve" style="color: #eab308;"></ha-icon>
                    <div class="stat-info"><div class="stat-label">TỐC ĐỘ TỐI ƯU</div><div class="stat-val" id="vf-stat-speed">--</div></div>
                  </div>
                </div>

                <div class="stat-detail-container" id="detail-container-2">
                    <div class="stat-detail-content" id="detail-eff">
                        <div class="detail-row"><span>Tổng điện vòng đời:</span> <b id="dt-total-kwh" style="color:#f59e0b;">--</b></div>
                        <div class="detail-row"><span>Tổng tiền sạc:</span> <b id="dt-total-cost">--</b></div>
                    </div>
                    <div class="stat-detail-content" id="detail-speed">
                        <div style="font-size:10px; color:#64748b; margin-bottom:6px;">Phân tích theo dải tốc độ:</div>
                        <div id="dt-speed-chart" style="display:flex; flex-direction:column; gap:4px;">Chưa đủ dữ liệu AI</div>
                    </div>
                </div>

                <div class="stat-box clickable" id="box-trip">
                  <div class="box-main">
                    <ha-icon icon="mdi:map-marker-path" style="color: #8b5cf6;"></ha-icon>
                    <div class="stat-info"><div class="stat-label">TRIP HIỆN TẠI</div><div class="stat-val" id="vf-stat-trip">--</div></div>
                  </div>
                </div>
                <div class="stat-box clickable" id="box-charge" style="background:rgba(251, 191, 36, 0.1); border-color:rgba(245, 158, 11, 0.3);">
                  <div class="box-main">
                    <ha-icon icon="mdi:ev-station" style="color: #f59e0b;"></ha-icon>
                    <div class="stat-info"><div class="stat-label">LỊCH SỬ SẠC</div><div class="stat-val" id="vf-stat-charge-count">--</div></div>
                  </div>
                </div>

                <div class="stat-detail-container" id="detail-container-3">
                    <div class="stat-detail-content" id="detail-trip">
                        <div class="detail-row"><span>Từ:</span> <b id="dt-trip-start" style="color:#64748b; font-size:11px;">--</b></div>
                        <div class="detail-row"><span>Tốc độ trung bình:</span> <b id="dt-trip-avg-speed">--</b></div>
                        <div class="detail-row"><span>Tiêu thụ chuyến:</span> <b id="dt-trip-energy" style="color:#eab308;">--</b></div>
                    </div>
                    <div class="stat-detail-content" id="detail-charge" style="padding:0; overflow:hidden;">
                        <div style="padding:15px; border-bottom:1px solid #e2e8f0; display:flex; gap:10px; background:#f8fafc;">
                            <div style="flex:1; background:white; padding:10px; border-radius:8px; border:1px solid #e2e8f0; text-align:center;">
                                <div style="font-size:10px; color:#64748b; font-weight:bold;">SẠC TRẠM</div>
                                <div style="font-size:18px; font-weight:900; color:#2563eb;" id="inline-pub-sessions">--</div>
                            </div>
                            <div style="flex:1; background:white; padding:10px; border-radius:8px; border:1px solid #e2e8f0; text-align:center;">
                                <div style="font-size:10px; color:#64748b; font-weight:bold;">SẠC NHÀ</div>
                                <div style="font-size:18px; font-weight:900; color:#10b981;"><span id="inline-home-sessions">--</span><span style="font-size:11px; font-weight:normal; color:#64748b;"> lần</span></div>
                                <div style="font-size:10px; color:#10b981; font-weight:bold; margin-top:2px;"><span id="inline-home-kwh">--</span> kWh</div>
                            </div>
                        </div>
                        <div style="padding:10px 15px; font-size:11px; font-weight:bold; color:#94a3b8; text-transform:uppercase; background:white;">Lần sạc gần nhất</div>
                        <div id="vf-inline-charge-list" style="max-height: 200px; overflow-y: auto; background:white; padding:0 15px 10px 15px;"></div>
                    </div>
                </div>

              </div> <div id="vf-ai-advisor-container" style="display: none; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); border-radius: 16px; padding: 15px; margin-bottom: 15px; color: white; box-shadow: 0 4px 15px rgba(37,99,235,0.2);">
                  <div style="display: flex; align-items: center; gap: 8px; font-weight: bold; font-size: 14px; margin-bottom: 8px;">
                      <ha-icon icon="mdi:robot-outline" style="color: #60a5fa;"></ha-icon>
                      Chuyên gia AI Đánh giá
                  </div>
                  <div id="vf-ai-text" style="font-size: 12px; line-height: 1.5; color: #e2e8f0; font-style: italic;">
                      Đang chờ phân tích chuyến đi...
                  </div>
              </div>

              <div id="vf-smart-suggestion" style="display:none; position:absolute; bottom:60px; left:50%; transform:translateX(-50%); background:rgba(255,255,255,0.95); backdrop-filter:blur(10px); padding:12px; border-radius:16px; box-shadow:0 10px 25px rgba(0,0,0,0.2); width:85%; z-index:1000; border:2px solid #f59e0b;">
                 <div style="font-size:11px; color:#f59e0b; font-weight:800; margin-bottom:4px; display:flex; align-items:center; gap:4px;"><ha-icon icon="mdi:alert" style="--mdc-icon-size:14px;"></ha-icon> PIN THẤP - GỢI Ý SẠC TRÊN TUYẾN</div>
                 <div id="vf-suggest-name" style="font-size:14px; font-weight:bold; color:#1e3a8a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">--</div>
                 <div style="font-size:12px; color:#475569; margin-top:2px;">Phía trước <b id="vf-suggest-dist">--</b> km • <b id="vf-suggest-power">--</b> kW • Trống: <b id="vf-suggest-avail" style="color:#16a34a;">--</b></div>
                 <button id="btn-suggest-nav" style="margin-top:8px; width:100%; background:#2563eb; color:white; border:none; border-radius:8px; padding:6px; font-weight:bold; cursor:pointer;">Dẫn đường ngay</button>
              </div>

              <div class="vf-map-container" style="position:relative; border-radius:16px; overflow:hidden; margin-top:10px; border:1px solid #e5e7eb; display:flex; flex-direction:column;">
                <div style="position:absolute; top:12px; left:12px; z-index:400; width: 70%; max-width: 300px;">
                    <select id="trip-selector" style="width:100%; background:rgba(255,255,255,0.95); backdrop-filter:blur(4px); border:2px solid #2563eb; border-radius:8px; padding:8px; font-size:12px; font-weight:bold; color:#1e3a8a; cursor:pointer;"><option value="current">Đang tải...</option></select>
                </div>
                <div id="vf-map-canvas" style="width:100%; height:350px; background:#e5e7eb; z-index:1;"></div>
                <div class="vf-address-bar" id="vf-address-container"><ha-icon icon="mdi:map-marker-radius"></ha-icon><span id="vf-current-address">Đang tải dữ liệu...</span></div>
                <div class="map-controls">
                  <button class="map-btn" id="btn-locate"><ha-icon icon="mdi:crosshairs-gps"></ha-icon></button>
                  <div style="height:1px;background:#ccc;margin:4px 0;"></div>
                  <button class="map-btn" id="btn-stations"><ha-icon icon="mdi:ev-station" style="color:#f59e0b;"></ha-icon></button>
                  <button class="map-btn" id="btn-filter-station" style="font-weight:900; font-size:11px; color:#f59e0b;">ALL</button>
                  <div style="height:1px;background:#ccc;margin:4px 0;"></div>
                  <button class="map-btn" id="btn-replay"><ha-icon id="icon-replay" icon="mdi:play-circle" style="color:#2563eb;"></ha-icon></button>
                </div>
              </div>

            </div>
          </ha-card>
        `;

        const style = document.createElement('style');
        style.textContent = `
          @import url('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css');
          .vf-card { isolation: isolate; border-radius: 24px; overflow: hidden; background: var(--card-background-color, #ffffff); box-shadow: 0 4px 20px rgba(0,0,0,0.05); font-family: -apple-system, sans-serif;}
          .vf-card-container { padding: 20px; }
          .vf-header { display: flex; justify-content: space-between; margin-bottom: 10px; }
          .vf-title { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; color: var(--primary-text-color);} .vf-title svg {width: 24px; color: #2563eb;}
          .vf-odo { text-align: right; } .vf-odo-label {font-size: 10px; font-weight: 800; color: #2563eb;} .vf-odo-value {font-size: 24px; font-weight: 800; color: var(--primary-text-color);}
          .vf-car-stage { position: relative; height: 220px; display: flex; justify-content: center; align-items: center; margin-bottom: 5px; transition: filter 0.3s;}
          .vf-car-stage.low-battery { filter: drop-shadow(0 0 15px rgba(239,68,68,0.3)); }
          .vf-car-stage img { max-width: 90%; max-height: 100%; filter: drop-shadow(0 20px 20px rgba(0,0,0,0.2)); z-index: 1;}
          .vf-status-badge { position: absolute; top: -10px; right: 0; background: #2563eb; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; z-index: 5;}
          .vf-tire { position: absolute; background: rgba(255,255,255,0.85); backdrop-filter: blur(8px); padding: 4px 8px; border-radius: 12px; border: 1px solid #e5e7eb; font-size: 11px; font-weight: 800; color: #1f2937; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); z-index: 5; }
          .vf-tire ha-icon { --mdc-icon-size: 14px; color: #6b7280; } .tire-unit { font-size: 9px; font-weight: 600; color: #6b7280; }
          .vf-tire-fl { bottom: 10%; left: 0; } .vf-tire-fr { top: 15%; left: 0; } .vf-tire-rl { bottom: 10%; right: 0; } .vf-tire-rr { top: 15%; right: 0; }
          .vf-controls-area { display: flex; justify-content: center; gap: 16px; margin-bottom: 12px; align-items: center;}
          .vf-gears { display: flex; background: rgba(243,244,246,0.8); padding: 8px 20px; border-radius: 30px; gap: 20px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);}
          .gear { font-size: 16px; font-weight: 800; color: #9ca3af; transition: all 0.3s; position: relative;} 
          .gear.active {color: #2563eb; transform: scale(1.2);} .gear.active::after { content: ''; position: absolute; bottom: -4px; left: 50%; transform: translateX(-50%); width: 4px; height: 4px; background: #2563eb; border-radius: 50%; }
          .vf-speed { display: flex; align-items: baseline; background: rgba(37,99,235,0.1); border: 2px solid rgba(37,99,235,0.3); padding: 6px 20px; border-radius: 30px;}
          .vf-speed span:first-child { font-size: 28px; font-weight: 900; color: #2563eb; } .vf-speed-unit { font-size: 11px; font-weight: bold; color: #2563eb; margin-left: 4px;}
          .vf-doors-status { display: flex; gap: 8px; justify-content: center; width: 100%; flex-wrap: wrap; margin-bottom: 15px;}
          .door-badge { display: flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: bold; background: rgba(255,255,255,0.95); border: 1px solid #e5e7eb; box-shadow: 0 2px 6px rgba(0,0,0,0.1); color: #374151;}
          .door-badge.open { background: #fee2e2; border-color: #ef4444; color: #b91c1c; animation: pulseRed 1.5s infinite; }
          .door-badge.open.warning { background: #fffbeb; border-color: #f59e0b; color: #d97706; animation: pulseOrange 2s infinite; }
          .door-badge ha-icon { --mdc-icon-size: 15px; }
          @keyframes pulseRed { 0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); } 70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }
          @keyframes pulseOrange { 0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); } 70% { box-shadow: 0 0 0 6px rgba(245, 158, 11, 0); } 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); } }
          
          .vf-charging-banner { display: flex; align-items: center; justify-content: space-between; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 15px 20px; border-radius: 16px; margin-bottom: 16px; animation: pulseChargeGlow 2.5s infinite; }
          .charging-left { display: flex; flex-direction: column; gap: 4px; }
          .charging-title { font-size: 15px; font-weight: 800; display:flex; align-items:center; gap:8px; line-height: 1.2;}
          .charging-title ha-icon { --mdc-icon-size: 20px; }
          .charging-details { font-size: 12px; display:flex; align-items:center; opacity: 0.9;}
          .charging-right { display: flex; align-items: baseline; gap: 4px; text-align: right;}
          .charging-time { font-size: 28px; font-weight: 900; line-height: 1;}
          .charging-time-label { font-size: 11px; display: flex; flex-direction: column; text-align: left; line-height: 1.2; opacity: 0.9;}
          
          @keyframes pulseChargeGlow { 0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); } 70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); } 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }
          .vf-remote-bar { display: flex; justify-content: center; gap: 15px; margin-bottom: 20px; padding: 10px; background: rgba(243,244,246,0.5); border-radius: 16px;}
          .remote-btn { display: flex; align-items: center; justify-content: center; width: 45px; height: 45px; background: white; border: 1px solid #e5e7eb; border-radius: 50%; color: #4b5563; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: all 0.2s ease;}
          .remote-btn ha-icon { --mdc-icon-size: 22px; } .remote-btn:hover { background: #eff6ff; color: #2563eb; transform: translateY(-2px);}
          
          .vf-stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
          
          .stat-box { display: flex; align-items: center; gap: 8px; background: rgba(243, 244, 246, 0.6); padding: 10px; border-radius: 12px; border: 1px solid rgba(229, 231, 235, 0.8); transition: all 0.2s; cursor: pointer; height: 60px; box-sizing: border-box; }
          .stat-box:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); background: white; }
          .stat-box.active-box { border-color: #2563eb; background: white; box-shadow: 0 4px 12px rgba(37,99,235,0.15); transform: translateY(-2px); }
          
          .box-main { display: flex; align-items: center; gap: 8px; width: 100%; }
          .box-main ha-icon { flex-shrink: 0; --mdc-icon-size: 22px; }
          .stat-info { display: flex; flex-direction: column; min-width: 0; width: 100%; justify-content: center; overflow: hidden;}
          .stat-label { font-size: 10px; font-weight: 700; color: #6b7280; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px; transition: color 0.3s;}
          .stat-val { font-size: 15px; font-weight: 800; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
          .stat-unit { font-size: 0.7em; font-weight: 600; color: #6b7280; margin-left: 3px; }
          
          .stat-detail-container { grid-column: 1 / -1; display: none; animation: slideDown 0.2s ease-out; transform-origin: top; margin-top: -5px; }
          .stat-detail-content { background: #f8fafc; border-radius: 12px; padding: 15px; border: 1px solid #93c5fd; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02); display: none; }
          
          .detail-row { display: flex; justify-content: space-between; font-size: 12px; color: #475569; padding: 6px 0; border-bottom: 1px dashed #e2e8f0; }
          .detail-row:last-child { border-bottom: none; padding-bottom: 0; }
          @keyframes slideDown { from { opacity: 0; transform: scaleY(0.95); } to { opacity: 1; transform: scaleY(1); } }
          
          .vf-address-bar { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 12px; font-size: 13px; font-weight: 600; color: #475569;}
          .vf-address-bar ha-icon { color: #ef4444; animation: bouncePin 2s infinite;}
          @keyframes bouncePin { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
          .map-controls { position: absolute; top: 12px; right: 12px; z-index: 400; display: flex; flex-direction: column; gap: 6px; }
          .map-btn { width: 32px; height: 32px; background: white; border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; cursor: pointer; display:flex; align-items:center; justify-content:center;}
        `;
        this.appendChild(style);
        this.content = true;

        this.toggleExpand = (boxId, detailId, containerId) => {
            const box = this.querySelector(boxId);
            const detail = this.querySelector(detailId);
            const container = this.querySelector(containerId);
            
            if (!box || !detail || !container) return;
            
            const isExpanded = box.classList.contains('active-box');
            
            this.querySelectorAll('.stat-box').forEach(el => el.classList.remove('active-box'));
            this.querySelectorAll('.stat-detail-container').forEach(el => el.style.display = 'none');
            this.querySelectorAll('.stat-detail-content').forEach(el => el.style.display = 'none');
            
            if (!isExpanded) {
                box.classList.add('active-box');
                container.style.display = 'block';
                detail.style.display = 'block';
                
                if (boxId === '#box-charge') {
                    this.renderChargeHistory();
                }
            }
        };

        this.renderChargeHistory = () => {
            const listEl = this.querySelector('#vf-inline-charge-list');
            if (!listEl) return;
            let html = '';
            if (this._chargeHistoryData && this._chargeHistoryData.length > 0) {
                this._chargeHistoryData.forEach(c => {
                    html += `
                    <div style="padding:8px 0; border-bottom:1px solid #e5e7eb;">
                        <div style="font-weight:bold; font-size:11px; color:#1e3a8a; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${c.address}</div>
                        <div style="display:flex; justify-content:space-between; font-size:10px; color:#475569;">
                            <span>${c.date}</span>
                            <span style="color:#d97706; font-weight:bold;">${c.kwh} kWh</span>
                            <span>${c.duration}p</span>
                        </div>
                    </div>`;
                });
            } else {
                html = `<div style="padding:10px; text-align:center; color:#6b7280; font-size:11px;">Chưa có dữ liệu sạc trạm.</div>`;
            }
            const pSessions = this.querySelector('#inline-pub-sessions');
            const hSessions = this.querySelector('#inline-home-sessions');
            const hKwh = this.querySelector('#inline-home-kwh');
            
            if(pSessions) pSessions.innerText = this._backendData.api_total_charge_sessions || 0;
            if(hSessions) hSessions.innerText = this._backendData.api_home_charge_sessions || 0;
            if(hKwh) hKwh.innerText = this._backendData.api_home_charge_kwh || 0;
            
            listEl.innerHTML = html;
        };

        const attachClick = (boxId, detailId, containerId) => {
            const el = this.querySelector(boxId);
            if (el) el.onclick = () => this.toggleExpand(boxId, detailId, containerId);
        };
        
        attachClick('#box-batt', '#detail-batt', '#detail-container-1');
        attachClick('#box-range', '#detail-range', '#detail-container-1');
        attachClick('#box-eff', '#detail-eff', '#detail-container-2');
        attachClick('#box-speed', '#detail-speed', '#detail-container-2'); 
        attachClick('#box-trip', '#detail-trip', '#detail-container-3');
        attachClick('#box-charge', '#detail-charge', '#detail-container-3'); 

        const btnLocate = this.querySelector('#btn-locate');
        if (btnLocate) btnLocate.onclick = () => { 
          if(this._map && this._lastLat) this._map.setView([this._lastLat, this._lastLon], 15, {animate: true});
        };

        const btnStations = this.querySelector('#btn-stations');
        if (btnStations) btnStations.onclick = () => {
          this._hass.callService('button', 'press', { entity_id: `button.${p}_tim_tram_sac` });
        };
        
        const btnFilter = this.querySelector('#btn-filter-station');
        if(btnFilter) {
            btnFilter.onclick = () => {
                if (this._stationFilter === 'ALL') { this._stationFilter = 'DC'; btnFilter.innerText = 'DC'; btnFilter.style.color = '#dc2626'; }
                else if (this._stationFilter === 'DC') { this._stationFilter = 'AC'; btnFilter.innerText = 'AC'; btnFilter.style.color = '#16a34a'; }
                else { this._stationFilter = 'ALL'; btnFilter.innerText = 'ALL'; btnFilter.style.color = '#f59e0b'; }
                this.renderStations();
            };
        }

        const callServiceBtn = (btnId, domain, service, entityId) => {
            const btn = this.querySelector(btnId);
            if(btn) btn.onclick = () => {
                if(this._hass.states[entityId]) this._hass.callService(domain, service, { entity_id: entityId });
            };
        };
        callServiceBtn('#btn-rc-lock', 'button', 'press', `button.${p}_khoa_cua`);
        callServiceBtn('#btn-rc-unlock', 'button', 'press', `button.${p}_mo_cua`);
        callServiceBtn('#btn-rc-horn', 'button', 'press', `button.${p}_bam_coi`);
        callServiceBtn('#btn-rc-lights', 'button', 'press', `button.${p}_nhay_den`);

        const selectEl = this.querySelector('#trip-selector');
        if(selectEl) {
            selectEl.onchange = (e) => {
                const val = e.target.value;
                let rawPoints = [];
                if (val === "current") {
                    const rs = this._hass.states[`sensor.${p}_lo_trinh_gps`];
                    if (rs && rs.attributes && rs.attributes.route_points) {
                        try { rawPoints = typeof rs.attributes.route_points === 'string' ? JSON.parse(rs.attributes.route_points) : rs.attributes.route_points; } catch(err){}
                    }
                } else {
                    rawPoints = this._tripHistory[parseInt(val)]?.route || [];
                }
                this._selectedRouteCoords = this.cleanRouteData(rawPoints);
                this._currentPolylineString = JSON.stringify(this._selectedRouteCoords);
                
                if(this._polyline) {
                    this._polyline.setLatLngs(this._selectedRouteCoords);
                    if (this._selectedRouteCoords.length > 1) this._map.fitBounds(this._polyline.getBounds(), {padding: [30, 30]});
                }
            };
        }

        const btnReplay = this.querySelector('#btn-replay');
        const iconReplay = this.querySelector('#icon-replay');
        
        if(btnReplay && iconReplay) {
            btnReplay.onclick = () => {
                if (!this._map || !this._marker || !this._polyline) return;
                if (this._selectedRouteCoords.length < 2) return alert("Lộ trình quá ngắn!");

                if (this._isReplaying) {
                    clearInterval(this._replayTimer);
                    this._isReplaying = false;
                    iconReplay.setAttribute('icon', 'mdi:play-circle');
                    if(this._lastLat) this._map.setView([this._lastLat, this._lastLon], 15);
                } else {
                    this._isReplaying = true;
                    iconReplay.setAttribute('icon', 'mdi:stop-circle');
                    
                    let currentIdx = 0;
                    this._replayTimer = setInterval(() => {
                        if (currentIdx >= this._selectedRouteCoords.length) {
                            clearInterval(this._replayTimer);
                            this._isReplaying = false;
                            iconReplay.setAttribute('icon', 'mdi:play-circle');
                            return;
                        }
                        const pt = this._selectedRouteCoords[currentIdx];
                        if (pt && pt.length >= 2) {
                            let targetAngle = this._currentAngle || 0;
                            if (currentIdx < this._selectedRouteCoords.length - 1) {
                                targetAngle = this.getBearing(pt[0], pt[1], this._selectedRouteCoords[currentIdx + 1][0], this._selectedRouteCoords[currentIdx + 1][1]);
                            } else if (currentIdx > 0) {
                                targetAngle = this.getBearing(this._selectedRouteCoords[currentIdx - 1][0], this._selectedRouteCoords[currentIdx - 1][1], pt[0], pt[1]);
                            }
                            
                            const simGear = pt.length > 3 ? pt[3] : 4;
                            if (simGear == 2) targetAngle = (targetAngle + 180) % 360;
                            
                            const smoothedAngle = this._smoothRotation(targetAngle);

                            this._marker.setLatLng([pt[0], pt[1]]);
                            this._map.panTo([pt[0], pt[1]], { animate: true, duration: 0.25 });

                            const iconEl = this._marker.getElement();
                            if (iconEl) {
                                const svg = iconEl.querySelector('.car-dir-svg');
                                if (svg) svg.style.transform = `rotate(${smoothedAngle}deg)`;
                                
                                const badge = iconEl.querySelector('.car-speed-badge');
                                if (badge) {
                                    badge.style.display = pt.length > 2 && pt[2] > 0 ? 'block' : 'none';
                                    badge.innerText = pt.length > 2 ? `${pt[2]} km/h` : '';
                                }
                            }
                        }
                        currentIdx++;
                    }, 250); 
                }
            };
        }
      }

      let trackerLat = null;
      let trackerLon = null;
      const trackerObj = hass.states[`device_tracker.${p}_vi_tri_gps`];
      if (trackerObj && trackerObj.attributes) {
          trackerLat = trackerObj.attributes.latitude;
          trackerLon = trackerObj.attributes.longitude;
      }
      const lat = trackerLat;
      const lon = trackerLon;

      const name = getValidState(`sensor.${p}_ten_dinh_danh_xe`) || 'Xe VinFast';
      const statusObj = hass.states[`sensor.${p}_trang_thai_hoat_dong`];
      let statusTextRaw = statusObj ? statusObj.state : 'N/A';
      let statusText = statusTextRaw;
      
      if (statusObj && statusObj.last_changed) {
          statusText += ` ${formatTimeSince(statusObj.last_changed)}`;
      }
      
      const aiAdvisorObj = hass.states[`sensor.${p}_co_van_xe_dien_ai`];
      const aiContainer = this.querySelector('#vf-ai-advisor-container');
      const aiTextEl = this.querySelector('#vf-ai-text');
      
      if (aiContainer && aiTextEl) {
          if (aiAdvisorObj && aiAdvisorObj.state && 
              aiAdvisorObj.state !== 'unknown' && 
              aiAdvisorObj.state !== 'unavailable' &&
              !aiAdvisorObj.state.includes('Hệ thống AI đang chờ') &&
              !aiAdvisorObj.state.includes('Vui lòng nhập Google Gemini')) {
              
              aiTextEl.innerText = aiAdvisorObj.state;
              aiContainer.style.display = 'block'; 
          } else {
              aiContainer.style.display = 'none'; 
          }
      }
      
      const gear = getValidState(`sensor.${p}_vi_tri_can_so`) || 'P';
      const speed = getValidState(`sensor.${p}_toc_do_hien_tai`) || '0';
      const speedNum = Math.round(Number(speed));
      
      const nameEl = this.querySelector('#vf-name');
      const statBadgeEl = this.querySelector('#vf-status-badge');
      if(nameEl) nameEl.innerText = name;
      if(statBadgeEl) statBadgeEl.innerText = statusText;
      
      const odoRaw = getValidState(`sensor.${p}_tong_odo`);
      const odoEl = this.querySelector('#vf-odo-int');
      if(odoEl) odoEl.innerText = (odoRaw && !isNaN(odoRaw)) ? Math.floor(parseFloat(odoRaw)).toString() : '--';

      let rawImage = getValidState(`sensor.${p}_hinh_anh_xe_url`);
      const imgEl = this.querySelector('#vf-car-img');
      if (imgEl && rawImage && rawImage !== 'unknown') imgEl.src = rawImage;

      const updateTire = (id, val) => {
        const el = this.querySelector(id);
        if(el) {
          if (val !== null && val !== 'unknown' && val !== '') { el.style.display = 'block'; el.querySelector('span').innerText = val; }
          else { el.style.display = 'none'; }
        }
      };
      updateTire('#tire-fl', getValidState(`sensor.${p}_ap_suat_lop_truoc_trai`)); 
      updateTire('#tire-fr', getValidState(`sensor.${p}_ap_suat_lop_truoc_phai`)); 
      updateTire('#tire-rl', getValidState(`sensor.${p}_ap_suat_lop_sau_trai`)); 
      updateTire('#tire-rr', getValidState(`sensor.${p}_ap_suat_lop_sau_phai`));

      ['P','R','N','D'].forEach(g => {
        const el = this.querySelector(`#gear-${g}`);
        if(el) { if (gear.includes(g)) el.classList.add('active'); else el.classList.remove('active'); }
      });
      
      const speedEl = this.querySelector('#vf-speed-container');
      if (!this._isReplaying && speedEl) {
          const speedDisplayEl = this.querySelector('#vf-speed');
          if (gear.includes('P') || speedNum === 0) {
              speedEl.style.display = 'none';
          } else { 
              speedEl.style.display = 'flex'; 
              if (speedDisplayEl) speedDisplayEl.innerText = speedNum; 
          }
      }

      const checkSensorState = (slugs, targetState) => {
          for (let s of slugs) {
              const state = getValidState(`sensor.${p}_${s}`);
              if (state && state.toLowerCase() === targetState.toLowerCase()) return true;
          }
          return false;
      };

      const doorsConfig = [
          { slugs: ['cua_truoc_trai', 'cua_tai_xe'], name: 'Cửa lái', icon: 'mdi:car-door' },
          { slugs: ['cua_truoc_phai', 'cua_phu'], name: 'Cửa phụ', icon: 'mdi:car-door' },
          { slugs: ['cua_sau_trai'], name: 'Cửa sau T', icon: 'mdi:car-door' },
          { slugs: ['cua_sau_phai'], name: 'Cửa sau P', icon: 'mdi:car-door' },
          { slugs: ['cop_sau'], name: 'Cốp sau', icon: 'mdi:car-back' },
          { slugs: ['nap_capo', 'capo'], name: 'Capo', icon: 'mdi:car' },
          { slugs: ['cua_so_tai_xe', 'cua_so_truoc_trai'], name: 'Kính lái', icon: 'mdi:window-open' }
      ];

      const openDoors = doorsConfig.filter(d => checkSensorState(d.slugs, 'mở'));
      const isParked = statusTextRaw.toLowerCase().includes('đỗ') || gear.includes('P');
      const isUnlocked = checkSensorState(['khoa_tong', 'khoa_cua'], 'mở khóa');
      
      let hasSystemError = false;
      for (let s of ['canh_bao_loi', 'trang_thai_loi', 'loi_he_thong']) {
          const state = getValidState(`sensor.${p}_${s}`);
          if (state && state.toLowerCase() !== 'bình thường' && state.toLowerCase() !== 'khong' && state !== '0' && state !== 'unknown') {
              hasSystemError = state; break;
          }
      }

      const doorsEl = this.querySelector('#vf-doors-container');
      if (doorsEl) {
          let securityHtml = '';
          if (openDoors.length === 0 && (!isParked || !isUnlocked) && !hasSystemError) {
              securityHtml = `<div class="door-badge" style="color: #10b981; border-color: rgba(16, 185, 129, 0.3); background: rgba(255,255,255,0.7);"><ha-icon icon="mdi:shield-check-outline"></ha-icon> An toàn</div>`;
          } else {
              if (hasSystemError) securityHtml += `<div class="door-badge open" style="background: #fef2f2; border-color: #ef4444; color: #b91c1c;"><ha-icon icon="mdi:alert"></ha-icon> Lỗi: ${hasSystemError}</div>`;
              if (openDoors.length > 0) securityHtml += openDoors.map(d => `<div class="door-badge open"><ha-icon icon="${d.icon}"></ha-icon> ${d.name}</div>`).join('');
              if (isParked && isUnlocked) securityHtml += `<div class="door-badge open warning"><ha-icon icon="mdi:lock-open-alert"></ha-icon> Chưa khóa xe</div>`;
          }
          doorsEl.innerHTML = securityHtml;
      }

      const chargingBanner = this.querySelector('#vf-charging-banner');
      const isCharging = statusTextRaw && (statusTextRaw.toLowerCase().includes('sạc') || statusTextRaw.toLowerCase().includes('hoàn tất'));
      
      if (isCharging && chargingBanner && !statusTextRaw.toLowerCase().includes('không')) {
          chargingBanner.style.display = 'flex';
          
          let chargeLimit = this._backendData.api_target_charge_limit;
          if (!chargeLimit || chargeLimit === 0 || chargeLimit === '0') {
              chargeLimit = getValidState(`sensor.${p}_gioi_han_sac_muc_tieu`) || getValidState(`sensor.${p}_muc_tieu_sac_target`) || '--';
          }
          const chargeTimeRemain = getValidState(`sensor.${p}_thoi_gian_sac_con_lai`);
          
          const chargeLimitEl = this.querySelector('#vf-charge-limit');
          const chargeTimeEl = this.querySelector('#vf-charge-time');
          const chargeStatusTextEl = this.querySelector('#vf-charge-status-text');
          
          if (chargeLimitEl) chargeLimitEl.innerText = chargeLimit !== '--' ? `${chargeLimit}%` : '--';
          if (chargeTimeEl) chargeTimeEl.innerText = (chargeTimeRemain && chargeTimeRemain !== 'unknown') ? `${chargeTimeRemain}` : '--';
          if (chargeStatusTextEl) chargeStatusTextEl.innerText = statusTextRaw.includes('đầy') ? "Đã sạc đầy" : "Hệ thống đang sạc";
          
          if (!this._powerFetchTimer) {
              this.fetchBackendState(vinStr);
              this._powerFetchTimer = setInterval(() => this.fetchBackendState(vinStr), 10000);
          } else {
              const powerEl = this.querySelector('#vf-charge-power');
              if (powerEl && this._backendData.api_live_charge_power !== undefined) {
                  let pwr = this._backendData.api_live_charge_power;
                  powerEl.innerText = pwr > 0 ? `${pwr} kW` : 'Đang tính...';
              }
          }
      } else if (chargingBanner) {
          chargingBanner.style.display = 'none';
          if (this._powerFetchTimer) { clearInterval(this._powerFetchTimer); this._powerFetchTimer = null; }
      }

      const batt = getValidState(`sensor.${p}_phan_tram_pin`);
      const range = getValidState(`sensor.${p}_quang_duong_du_kien`);
      const trip = getValidState(`sensor.${p}_quang_duong_chuyen_di_trip`);
      const tripEnergy = getValidState(`sensor.${p}_dien_nang_tieu_thu_trip`);
      
      const effKwh = getValidState(`sensor.${p}_hieu_suat_tieu_thu_trung_binh_xe`) || '--';
      const effRangePerPercent = getValidState(`sensor.${p}_quang_duong_di_duoc_moi_1_pin`) || '--';

      if (!this._effToggleTimer) {
          this._effToggleTimer = setInterval(() => {
              this._effToggleState = !this._effToggleState;
              const effEl = this.querySelector('#vf-stat-eff');
              const lblEl = this.querySelector('#lbl-eff');
              if (effEl && lblEl) {
                  effEl.style.opacity = 0;
                  setTimeout(() => {
                      if (this._effToggleState) {
                          effEl.innerHTML = `${effRangePerPercent}<span class="stat-unit">km/1%</span>`;
                          lblEl.innerText = "Mỗi 1% Pin";
                          lblEl.style.color = "#3b82f6";
                      } else {
                          effEl.innerHTML = `${effKwh}<span class="stat-unit">kWh/100km</span>`;
                          lblEl.innerText = "Hiệu suất TB";
                          lblEl.style.color = "#6b7280";
                      }
                      effEl.style.opacity = 1;
                      effEl.style.transition = "opacity 0.5s";
                  }, 300);
              }
          }, 5000);
      }

      const renderStat = (id, val, unit) => {
          const el = this.querySelector(id);
          if(el) {
              if (val && val !== 'unknown' && val !== '--' && val !== '0') el.innerHTML = `${val}<span class="stat-unit">${unit}</span>`;
              else el.innerHTML = '--';
          }
      };

      renderStat('#vf-stat-batt', batt, '%');
      renderStat('#vf-stat-range', range, 'km');
      renderStat('#vf-stat-trip', trip, 'km');
      
      const chargeCountEl = this.querySelector('#vf-stat-charge-count');
      if(chargeCountEl) {
          let count = this._backendData.api_total_charge_sessions || 0;
          chargeCountEl.innerHTML = `${count}<span class="stat-unit">lần</span>`;
      }

      const speedBandStr = getValidState(`sensor.${p}_dai_toc_do_toi_uu_nhat`);
      const speedElTarget = this.querySelector('#vf-stat-speed');
      if (speedElTarget) {
          if (speedBandStr && speedBandStr !== 'unknown' && speedBandStr !== '--') {
              let spd = speedBandStr.split(' ')[0];
              speedElTarget.innerHTML = `${spd}<span class="stat-unit">km/h</span>`;
          } else {
              speedElTarget.innerHTML = '--';
          }
      }

      const sohCalc = getValidState(`sensor.${p}_suc_khoe_pin_soh_tinh_toan`);
      const dtSohEl = this.querySelector('#dt-soh');
      if (dtSohEl) dtSohEl.innerText = sohCalc ? `${sohCalc}%` : '--';
      
      const dtChargeSocEl = this.querySelector('#dt-charge-soc');
      if (dtChargeSocEl) dtChargeSocEl.innerText = `${getValidState(`sensor.${p}_pin_luc_cam_sac_lan_cuoi`) || '?'}% ➔ ${getValidState(`sensor.${p}_pin_luc_rut_sac_lan_cuoi`) || '?'}%`;
      
      const dtRangeMaxEl = this.querySelector('#dt-range-max');
      if (dtRangeMaxEl) dtRangeMaxEl.innerText = `${getValidState(`sensor.${p}_quang_duong_cong_bo_max`) || '--'} km`;
      
      const dtRangeAiEl = this.querySelector('#dt-range-ai');
      if (dtRangeAiEl) dtRangeAiEl.innerText = `${getValidState(`sensor.${p}_quang_duong_thuc_te_day_100_pin`) || '--'} km`;
      
      const dtRangeDropEl = this.querySelector('#dt-range-drop');
      if (dtRangeDropEl) dtRangeDropEl.innerText = `${getValidState(`sensor.${p}_kha_nang_chai_pin_tham_khao`) || '--'} %`;

      const dtTotalKwhEl = this.querySelector('#dt-total-kwh');
      if (dtTotalKwhEl) dtTotalKwhEl.innerText = `${getValidState(`sensor.${p}_tong_dien_nang_da_sac`) || '--'} kWh`;
      
      const dtTotalCostEl = this.querySelector('#dt-total-cost');
      if (dtTotalCostEl) dtTotalCostEl.innerText = `${getValidState(`sensor.${p}_tong_chi_phi_sac_quy_doi`) || '--'} VNĐ`;

      let startAddr = (this._backendData.api_trip_start_address || "").split(',')[0];
      if (startAddr.length > 20) startAddr = startAddr.substring(0, 20) + '...';
      const dtTripStartEl = this.querySelector('#dt-trip-start');
      if (dtTripStartEl) dtTripStartEl.innerText = startAddr || '--';
      
      const dtTripAvgSpeedEl = this.querySelector('#dt-trip-avg-speed');
      if (dtTripAvgSpeedEl) dtTripAvgSpeedEl.innerText = `${getValidState(`sensor.${p}_toc_do_tb_chuyen_di`) || '--'} km/h`;
      
      const dtTripEnergyEl = this.querySelector('#dt-trip-energy');
      if (dtTripEnergyEl) dtTripEnergyEl.innerText = `${tripEnergy || '--'} kWh`;

      const spdSensor = hass.states[`sensor.${p}_dai_toc_do_toi_uu_nhat`];
      const dtSpeedChart = this.querySelector('#dt-speed-chart');
      if (dtSpeedChart && spdSensor && spdSensor.attributes) {
          let htmlChart = '';
          let maxVal = 0;
          let bars = [];
          for (let key in spdSensor.attributes) {
              if (key.includes('Dải')) {
                  let valStr = spdSensor.attributes[key];
                  let num = parseFloat(valStr.split(' ')[0]);
                  if (num > maxVal) maxVal = num;
                  bars.push({label: key.replace('Dải ', '').replace(' km/h', ''), val: num});
              }
          }
          if (bars.length > 0) {
              bars.forEach(b => {
                  let pct = Math.round((b.val / maxVal) * 100);
                  htmlChart += `<div style="display:flex; align-items:center; gap:8px;">
                      <div style="width:40px; font-size:10px; text-align:right; font-weight:bold; color:#475569;">${b.label}</div>
                      <div style="flex:1; background:#e2e8f0; height:8px; border-radius:4px; overflow:hidden;">
                          <div style="width:${pct}%; height:100%; background:${pct === 100 ? '#eab308' : '#3b82f6'}; transition: width 0.5s;"></div>
                      </div>
                      <div style="width:35px; font-size:10px; font-weight:bold; color:#1e3a8a;">${b.val}</div>
                  </div>`;
              });
              dtSpeedChart.innerHTML = htmlChart;
          }
      }

      const addressEl = this.querySelector('#vf-current-address');
      
      if (addressEl) {
          let backendAddr = this._backendData.api_current_address;
          let sensorAddress = getValidState(`sensor.${p}_dia_chi_hien_tai`) || getValidState(`sensor.${p}_vi_tri_xe`);

          let finalAddr = (backendAddr && !backendAddr.includes("Đang tải")) ? backendAddr : (sensorAddress && sensorAddress !== 'unknown' ? sensorAddress : null);

          if (finalAddr) {
               addressEl.innerText = finalAddr;
          } else if (lat && lon) {
              addressEl.innerText = `Tọa độ: ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
          } else {
              addressEl.innerText = "Không có tín hiệu GPS";
          }
      }

      if (batt && !isNaN(batt)) {
          const battNum = parseFloat(batt);
          const stageEl = this.querySelector('#vf-car-stage');
          const boxBatt = this.querySelector('#box-batt');
          
          if (battNum < 20) {
              if (stageEl) stageEl.classList.add('low-battery');
              if (boxBatt) boxBatt.style.background = '#fef2f2';
          } else {
              if (stageEl) stageEl.classList.remove('low-battery');
              if (boxBatt) {
                  boxBatt.style.background = boxBatt.classList.contains('active-box') ? 'white' : 'rgba(243, 244, 246, 0.6)';
              }
          }

          if (this._selectedRouteCoords.length >= 2) {
              const lastPt = this._selectedRouteCoords[this._selectedRouteCoords.length - 1];
              const prevPt = this._selectedRouteCoords[this._selectedRouteCoords.length - 2];
              const currentHeading = this.getBearing(prevPt[0], prevPt[1], lastPt[0], lastPt[1]);
              this.checkAndShowSmartSuggestion(battNum, currentHeading);
          } else {
              this.checkAndShowSmartSuggestion(battNum, null);
          }
      }

      if (this._map && lat && lon && typeof L !== 'undefined') {
        if (!this._isReplaying) {
            let targetAngle = null;

            if (this._lastHeadingLat === null) {
                this._lastHeadingLat = lat;
                this._lastHeadingLon = lon;
            } else {
                const distToLastHeading = this._map.distance([this._lastHeadingLat, this._lastHeadingLon], [lat, lon]);
                if (distToLastHeading > 2.0) {
                    targetAngle = this.getBearing(this._lastHeadingLat, this._lastHeadingLon, lat, lon);
                    if (gear.includes('R') || gear === '2') {
                        targetAngle = (targetAngle + 180) % 360;
                    }
                    this._lastHeadingLat = lat;
                    this._lastHeadingLon = lon;
                }
            }

            if (this._marker) {
                this._marker.setOpacity(1); 
                this._marker.setLatLng([lat, lon]);

                const iconEl = this._marker.getElement();
                if (iconEl) {
                    if (targetAngle !== null) {
                        const smoothedAngle = this._smoothRotation(targetAngle);
                        const svg = iconEl.querySelector('.car-dir-svg');
                        if (svg) svg.style.transform = `rotate(${smoothedAngle}deg)`;
                    }

                    const badge = iconEl.querySelector('.car-speed-badge');
                    if (badge) {
                        badge.style.display = (!gear.includes('P') && speedNum > 0) ? 'block' : 'none';
                        badge.innerText = `${speedNum} km/h`;
                    }
                }
            }

            if (this._lastLat === null) {
                this._map.setView([lat, lon], 15);
            }
            this._lastLat = lat; this._lastLon = lon;
            
            const selectEl = this.querySelector('#trip-selector');
            if (selectEl && selectEl.value === "current") {
                const routeSensor = hass.states[`sensor.${p}_lo_trinh_gps`];
                if (routeSensor && routeSensor.attributes && routeSensor.attributes.route_points && this._polyline) {
                    try { 
                        const newRouteStr = typeof routeSensor.attributes.route_points === 'string' ? routeSensor.attributes.route_points : JSON.stringify(routeSensor.attributes.route_points);
                        if (this._currentPolylineString !== newRouteStr) {
                            this._currentPolylineString = newRouteStr;
                            this._selectedRouteCoords = this.cleanRouteData(JSON.parse(newRouteStr));
                            this._polyline.setLatLngs(this._selectedRouteCoords);
                        }
                    } catch(e) { }
                }
            }
        }

        const stationSensor = hass.states[`sensor.${p}_tram_sac_lan_can`];
        if (stationSensor && stationSensor.attributes && stationSensor.attributes.stations) {
            try {
                let newStations = typeof stationSensor.attributes.stations === 'string' ? JSON.parse(stationSensor.attributes.stations) : stationSensor.attributes.stations;
                if (Array.isArray(newStations) && this._currentStations.length !== newStations.length) {
                    this._currentStations = newStations;
                    this.renderStations();
                }
            } catch(e) {}
        }
      }
    } catch (error) {
        console.error("VinFast Card Crash:", error);
        this.innerHTML = `<ha-card style="padding: 20px; color: red;"><b>Lỗi JavaScript Giao Diện:</b><br><pre style="white-space: pre-wrap; font-size: 11px; margin-top:10px;">${error.stack || error.message}</pre></ha-card>`;
    }
  }
  
  getCardSize() { return 8; }
}

if (!customElements.get('vinfast-digital-twin')) {
    customElements.define('vinfast-digital-twin', VinFastDigitalTwin);
}