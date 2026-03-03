class VinFastDigitalTwin extends HTMLElement {
  setConfig(config) {
    if (!config.entity_prefix) {
      throw new Error('Cần khai báo entity_prefix (VD: vf8_abcd1234)');
    }
    this.config = config;
    // Biến lưu trữ tọa độ để chống nháy bản đồ
    this._lastLat = null;
    this._lastLon = null;
  }

  set hass(hass) {
    this._hass = hass;
    const p = this.config.entity_prefix;

    // HÀM KIỂM TRA SỰ TỒN TẠI CỦA THỰC THỂ
    const getValidState = (entityId, defaultVal = null) => {
      const stateObj = hass.states[entityId];
      if (!stateObj || stateObj.state === 'unavailable' || stateObj.state === 'unknown') {
        return defaultVal;
      }
      return stateObj.state;
    };

    // 1. LẤY DỮ LIỆU CƠ BẢN
    const name = getValidState(`sensor.${p}_ten_dinh_danh_xe`, 'Xe VinFast');
    const odo = getValidState(`sensor.${p}_tong_odo`, '--');
    const image = getValidState(`sensor.${p}_hinh_anh_xe_url`, 'https://shop.vinfastauto.com/on/demandware.static/-/Sites-app_vinfast_vn-Library/default/dw15d3dc68/images/PDP/vf9/M/M.png');
    const status = getValidState(`sensor.${p}_trang_thai_hoat_dong`, 'N/A');
    
    // 2. LẤY DỮ LIỆU DI CHUYỂN
    const gear = getValidState(`sensor.${p}_vi_tri_can_so`, 'P');
    const speed = getValidState(`sensor.${p}_toc_do_hien_tai`, '0');
    
    // 3. LẤY DỮ LIỆU LỐP XE
    const tpFL = getValidState(`sensor.${p}_ap_suat_lop_truoc_trai`);
    const tpFR = getValidState(`sensor.${p}_ap_suat_lop_truoc_phai`);
    const tpRL = getValidState(`sensor.${p}_ap_suat_lop_sau_trai`);
    const tpRR = getValidState(`sensor.${p}_ap_suat_lop_sau_phai`);

    // 4. LẤY DỮ LIỆU PHÂN TÍCH PIN & SẠC
    const battery = getValidState(`sensor.${p}_phan_tram_pin`, '--');
    const range = getValidState(`sensor.${p}_quang_duong_du_kien`, '--');
    const chargeKwh = getValidState(`sensor.${p}_dien_nang_lay_tu_luoi_lan_cuoi`, '0');
    const chargeEff = getValidState(`sensor.${p}_hieu_suat_sac_thuc_te_lan_cuoi`, '--');

    // 5. LẤY DỮ LIỆU SMART PROFILING
    const tripDist = getValidState(`sensor.${p}_quang_duong_chuyen_di_trip`, '0');
    const tripEff = getValidState(`sensor.${p}_hieu_suat_tieu_thu_trip`, '0');
    const bestBand = getValidState(`sensor.${p}_dai_toc_do_toi_uu_nhat`, 'Đang thu thập...');
    const address = getValidState(`sensor.${p}_vi_tri_xe_dia_chi`, 'Đang định vị...');

    // 6. KIỂM TRA DÒNG XE VF 3 ĐỂ ẨN NÚT BẤM TỪ XA
    const isVF3 = p.toLowerCase().startsWith('vf3');
    const hasLock = !isVF3 && hass.states[`button.${p}_khoa_cua`] !== undefined;
    const hasUnlock = !isVF3 && hass.states[`button.${p}_mo_khoa_cua`] !== undefined;
    const hasAC = !isVF3 && hass.states[`button.${p}_bat_dieu_hoa`] !== undefined;

    // 7. LẤY CẢNH BÁO
    const warnings = [];
    if (getValidState(`sensor.${p}_cua_tai_xe`) === 'Mở') warnings.push('Cửa tài xế');
    if (getValidState(`sensor.${p}_cua_phu`) === 'Mở') warnings.push('Cửa phụ');
    if (getValidState(`sensor.${p}_cua_sau_trai`) === 'Mở') warnings.push('Cửa sau trái');
    if (getValidState(`sensor.${p}_cua_sau_phai`) === 'Mở') warnings.push('Cửa sau phải');
    if (getValidState(`sensor.${p}_cop_sau`) === 'Mở') warnings.push('Cốp mở');
    if (getValidState(`sensor.${p}_nap_capo`) === 'Mở') warnings.push('Capo mở');
    if (getValidState(`sensor.${p}_khoa_tong`) === 'Mở Khóa') warnings.push('Chưa khóa');

    let odoInt = odo; let odoDec = '';
    if (odo.includes('.')) {
      const parts = odo.split('.'); odoInt = parts[0]; odoDec = '.' + parts[1];
    }

    // =======================================================
    // KHỞI TẠO GIAO DIỆN LẦN ĐẦU
    // =======================================================
    if (!this.content) {
      this.innerHTML = `
        <ha-card class="vf-card">
          <div class="vf-card-container">
            
            <div class="vf-header">
              <div class="vf-title">
                <svg viewBox="0 0 512 512" fill="currentColor"><path d="M560 3586 c-132 -28 -185 -75 -359 -321 -208 -291 -201 -268 -201 -701 0 -361 3 -383 69 -470 58 -77 133 -109 311 -134 202 -29 185 -21 199 -84 14 -62 66 -155 119 -209 110 -113 277 -165 430 -133 141 29 269 125 328 246 l29 59 1115 0 1115 0 29 -59 c60 -123 201 -226 345 -250 253 -43 499 137 543 397 34 203 -77 409 -268 500 -69 33 -89 38 -172 41 -116 5 -198 -15 -280 -67 -116 -76 -195 -193 -214 -321 -6 -36 -12 -71 -14 -77 -5 -19 -2163 -19 -2168 0 -2 6 -8 41 -14 77 -19 128 -98 245 -214 321 -82 52 -164 72 -280 67 -82 -3 -103 -8 -168 -40 -41 -19 -94 -52 -117 -72 -55 -48 -115 -139 -137 -209 -21 -68 -13 -66 -196 -37 -69 11 -128 20 -132 20 -17 0 -82 67 -94 97 -10 23 -14 86 -14 228 l0 195 60 0 c48 0 63 4 80 22 22 24 26 58 10 88 -12 22 -61 40 -111 40 l-39 0 0 43 c1 23 9 65 18 93 20 58 264 406 317 453 43 37 120 61 198 61 52 0 58 -2 53 -17 -4 -10 -48 -89 -98 -177 -70 -122 -92 -170 -95 -205 -5 -56 19 -106 67 -138 l33 -23 1511 0 c867 0 1583 -4 1680 -10 308 -18 581 -60 788 -121 109 -32 268 -103 268 -119 0 -6 -27 -10 -60 -10 -68 0 -100 -21 -100 -66 0 -63 40 -84 161 -84 l79 0 0 -214 c0 -200 -1 -215 -20 -239 -13 -16 -35 -29 -58 -33 -88 -16 -113 -102 -41 -140 81 -41 228 49 259 160 8 29 11 119 8 292 l-3 249 -32 67 c-45 96 -101 152 -197 197 -235 112 -604 187 -1027 209 l-156 9 -319 203 c-176 112 -359 223 -409 246 -116 56 -239 91 -366 104 -149 15 -1977 12 -2049 -4z m800 -341 l0 -205 -335 0 -336 0 12 23 c7 12 59 104 116 205 l105 182 219 0 219 0 0 -205z m842 15 c14 -102 27 -193 27 -202 1 -17 -23 -18 -359 -18 l-360 0 0 198 c0 109 3 202 7 205 4 4 153 6 332 5 l326 -3 27 -185z m528 157 c52 -14 125 -38 161 -55 54 -24 351 -206 489 -299 l35 -23 -516 0 -516 0 -26 188 c-15 103 -27 196 -27 206 0 18 7 19 153 13 112 -5 177 -12 247 -30z m-1541 -1132 c115 -63 176 -174 169 -305 -16 -272 -334 -402 -541 -221 -20 18 -51 63 -69 99 -28 57 -33 77 -33 142 0 65 5 85 33 142 37 76 93 128 169 159 75 30 200 23 272 -16z m3091 16 c110 -42 192 -149 207 -269 18 -159 -101 -319 -264 -352 -134 -28 -285 47 -350 174 -37 72 -43 180 -14 257 35 91 107 162 200 195 55 20 162 17 221 -5z"></path></svg>
                <span id="vf-name"></span>
              </div>
              <div class="vf-odo">
                <div class="vf-odo-label">ODOMETER</div>
                <div class="vf-odo-value"><span id="vf-odo-int"></span><span class="vf-odo-dec" id="vf-odo-dec"></span> <span class="vf-odo-unit">km</span></div>
              </div>
            </div>

            <div class="vf-car-stage">
              <div id="vf-status-badge" class="vf-status-badge"></div>
              <img id="vf-car-img" src="" alt="Car">
              <div class="vf-tire vf-tire-fl" id="tire-fl"><ha-icon icon="mdi:tire"></ha-icon><br><span id="tp-fl"></span> bar</div>
              <div class="vf-tire vf-tire-fr" id="tire-fr"><ha-icon icon="mdi:tire"></ha-icon><br><span id="tp-fr"></span> bar</div>
              <div class="vf-tire vf-tire-rl" id="tire-rl"><ha-icon icon="mdi:tire"></ha-icon><br><span id="tp-rl"></span> bar</div>
              <div class="vf-tire vf-tire-rr" id="tire-rr"><ha-icon icon="mdi:tire"></ha-icon><br><span id="tp-rr"></span> bar</div>
            </div>

            <div class="vf-warnings-container" id="vf-warnings"></div>

            <div class="vf-controls-area">
              <div class="vf-gears">
                <span class="gear" id="gear-P">P</span>
                <span class="gear" id="gear-R">R</span>
                <span class="gear" id="gear-N">N</span>
                <span class="gear" id="gear-D">D</span>
              </div>
              <div class="vf-speed" id="vf-speed-container">
                <span id="vf-speed"></span> <span class="vf-speed-unit">km/h</span>
              </div>
            </div>

            <div class="vf-actions" id="vf-actions-container">
              <button class="vf-btn" id="btn-lock"><ha-icon icon="mdi:lock"></ha-icon> Khóa</button>
              <button class="vf-btn" id="btn-unlock"><ha-icon icon="mdi:lock-open"></ha-icon> Mở</button>
              <button class="vf-btn" id="btn-ac"><ha-icon icon="mdi:air-conditioner"></ha-icon> Đ.Hòa</button>
            </div>

            <div class="vf-analytics-grid">
              <div class="vf-stat-box">
                <ha-icon icon="mdi:battery-charging-100" style="color: #10b981;"></ha-icon>
                <div class="vf-stat-val"><span id="vf-battery"></span>%</div>
                <div class="vf-stat-sub" id="vf-range">-- km</div>
              </div>
              <div class="vf-stat-box">
                <ha-icon icon="mdi:ev-station" style="color: #f59e0b;"></ha-icon>
                <div class="vf-stat-val" style="font-size:16px"><span id="vf-charge-kwh"></span> kWh</div>
                <div class="vf-stat-sub">Hiệu suất <span id="vf-charge-eff"></span>%</div>
              </div>
              <div class="vf-stat-box">
                <ha-icon icon="mdi:map-marker-distance" style="color: #3b82f6;"></ha-icon>
                <div class="vf-stat-val" style="font-size:16px"><span id="vf-trip-dist"></span> km</div>
                <div class="vf-stat-sub"><span id="vf-trip-eff"></span> kWh/100km</div>
              </div>
              <div class="vf-stat-box" style="background: #f3e8ff;">
                <ha-icon icon="mdi:chart-bell-curve" style="color: #8b5cf6;"></ha-icon>
                <div class="vf-stat-val" style="font-size: 14px; line-height:1.2; padding-top:4px" id="vf-best-band"></div>
                <div class="vf-stat-sub" style="color: #8b5cf6;">Tốc độ tối ưu nhất</div>
              </div>
            </div>

            <div class="vf-map-container">
              <div class="vf-map-header">
                <ha-icon icon="mdi:map-marker-radius"></ha-icon>
                <span id="vf-address"></span>
              </div>
              <div id="vf-map-stage" style="width: 100%; height: 120px; background: #e5e7eb; display:flex; align-items:center; justify-content:center; color:#9ca3af; font-size:12px;">Đang tải bản đồ...</div>
            </div>

          </div>
        </ha-card>
      `;

      const style = document.createElement('style');
      style.textContent = `
        .vf-card { border-radius: 24px; overflow: hidden; background: var(--card-background-color, #ffffff); box-shadow: 0 4px 20px rgba(0,0,0,0.05); }
        .vf-card-container { padding: 20px; font-family: var(--primary-font-family, -apple-system, sans-serif); }
        .vf-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
        .vf-title { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; color: var(--primary-text-color); }
        .vf-title svg { width: 24px; height: 24px; color: #2563eb; }
        .vf-odo { text-align: right; }
        .vf-odo-label { font-size: 10px; font-weight: 800; color: #2563eb; letter-spacing: 1px; }
        .vf-odo-value { font-size: 20px; font-weight: 800; font-family: monospace; color: var(--primary-text-color); }
        .vf-odo-dec { color: var(--secondary-text-color); font-size: 14px; }
        
        .vf-car-stage { position: relative; width: 100%; height: 220px; display: flex; justify-content: center; align-items: center; margin-bottom: 20px; }
        .vf-car-stage img { max-width: 90%; max-height: 100%; object-fit: contain; filter: drop-shadow(0 20px 20px rgba(0,0,0,0.2)); z-index: 10; transition: transform 0.5s; }
        .vf-status-badge { position: absolute; top: -10px; right: 0; background: #2563eb; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; z-index:20;}
        
        .vf-tire { position: absolute; background: rgba(255,255,255,0.85); backdrop-filter: blur(8px); padding: 4px 8px; border-radius: 12px; border: 1px solid #e5e7eb; font-size: 11px; font-weight: 700; color: #374151; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); z-index: 20; }
        .vf-tire ha-icon { --mdc-icon-size: 14px; color: #6b7280; }
        .vf-tire-fl { bottom: 5%; left: 0; }
        .vf-tire-fr { top: 15%; left: 0; }
        .vf-tire-rl { bottom: 5%; right: 0; }
        .vf-tire-rr { top: 15%; right: 0; }

        .vf-warnings-container { min-height: 30px; display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; margin-bottom: 16px; }
        .vf-warning-badge { background: #fef2f2; border: 1px solid #fecaca; color: #ef4444; padding: 4px 10px; border-radius: 16px; font-size: 11px; font-weight: bold; display: flex; align-items: center; gap: 4px; animation: pulse 2s infinite; }
        .vf-safe-badge { background: #f0fdf4; border: 1px solid #bbf7d0; color: #16a34a; padding: 4px 10px; border-radius: 16px; font-size: 11px; font-weight: bold; display: flex; align-items: center; gap: 4px; }
        
        .vf-controls-area { display: flex; justify-content: center; gap: 16px; align-items: center; margin-bottom: 16px; }
        .vf-gears { display: flex; background: rgba(243,244,246,0.8); backdrop-filter: blur(8px); padding: 10px 20px; border-radius: 30px; gap: 20px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); }
        .gear { font-size: 16px; font-weight: 800; color: #9ca3af; transition: all 0.3s; position: relative; }
        .gear.active { color: #2563eb; transform: scale(1.2); }
        .gear.active::after { content: ''; position: absolute; bottom: -4px; left: 50%; transform: translateX(-50%); width: 4px; height: 4px; background: #2563eb; border-radius: 50%; }
        
        /* HIỂN THỊ TỐC ĐỘ TO VÀ RÕ RÀNG */
        .vf-speed { display: flex; align-items: baseline; background: rgba(37,99,235,0.1); border: 2px solid rgba(37,99,235,0.3); padding: 8px 24px; border-radius: 30px; }
        .vf-speed span:first-child { font-size: 32px; font-weight: 900; color: #2563eb; line-height: 1; }
        .vf-speed-unit { font-size: 12px; font-weight: bold; color: #2563eb; margin-left: 6px; text-transform: uppercase; }

        .vf-actions { display: flex; gap: 8px; margin-bottom: 20px; }
        .vf-btn { flex: 1; background: #f3f4f6; color: #374151; border: none; padding: 10px; border-radius: 12px; font-size: 13px; font-weight: bold; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 4px; transition: 0.2s; }
        .vf-btn:active { transform: scale(0.95); background: #e5e7eb; }
        .vf-btn ha-icon { color: #2563eb; }

        .vf-analytics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .vf-stat-box { background: #f9fafb; border-radius: 16px; padding: 12px; text-align: center; border: 1px solid #f3f4f6; }
        .vf-stat-box ha-icon { margin-bottom: 4px; }
        .vf-stat-val { font-size: 20px; font-weight: 800; color: #111827; }
        .vf-stat-sub { font-size: 11px; color: #6b7280; font-weight: 600; margin-top: 2px; }

        .vf-map-container { background: #f9fafb; border-radius: 16px; overflow: hidden; border: 1px solid #f3f4f6; }
        .vf-map-header { padding: 8px 12px; font-size: 11px; font-weight: 600; color: #4b5563; display: flex; align-items: center; gap: 4px; background: #f3f4f6; }
        .vf-map-iframe { width: 100%; height: 120px; border: none; pointer-events: none; }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
      `;
      this.appendChild(style);
      this.content = this.querySelector('.vf-card-container');

      // Nút bấm nếu có
      this.querySelector('#btn-lock')?.addEventListener('click', () => { this._hass.callService('button', 'press', { entity_id: `button.${p}_khoa_cua` }); });
      this.querySelector('#btn-unlock')?.addEventListener('click', () => { this._hass.callService('button', 'press', { entity_id: `button.${p}_mo_khoa_cua` }); });
      this.querySelector('#btn-ac')?.addEventListener('click', () => { this._hass.callService('button', 'press', { entity_id: `button.${p}_bat_dieu_hoa` }); });
    }

    // =======================================================
    // CẬP NHẬT DỮ LIỆU
    // =======================================================
    this.querySelector('#vf-name').innerText = name;
    this.querySelector('#vf-status-badge').innerText = status;
    this.querySelector('#vf-odo-int').innerText = odoInt;
    this.querySelector('#vf-odo-dec').innerText = odoDec;
    
    const imgEl = this.querySelector('#vf-car-img');
    if (imgEl.src !== image && image !== '') imgEl.src = image;

    // Lốp xe động
    const updateTire = (id, val) => {
      const el = this.querySelector(id);
      if (val !== null) { el.style.display = 'block'; el.querySelector('span').innerText = val; } 
      else { el.style.display = 'none'; }
    };
    updateTire('#tire-fl', tpFL); updateTire('#tire-fr', tpFR); updateTire('#tire-rl', tpRL); updateTire('#tire-rr', tpRR);

    // Ẩn/Hiện Nút bấm (Tự động giấu nếu là VF3)
    this.querySelector('#vf-actions-container').style.display = (hasLock || hasUnlock || hasAC) ? 'flex' : 'none';

    // Thống kê
    this.querySelector('#vf-battery').innerText = battery;
    this.querySelector('#vf-range').innerText = `${range} km`;
    this.querySelector('#vf-charge-kwh').innerText = chargeKwh;
    this.querySelector('#vf-charge-eff').innerText = chargeEff;
    this.querySelector('#vf-trip-dist').innerText = tripDist;
    this.querySelector('#vf-trip-eff').innerText = tripEff;
    this.querySelector('#vf-best-band').innerText = bestBand.split(' (')[0]; 
    this.querySelector('#vf-address').innerText = address;

    // GEARS
    ['P','R','N','D'].forEach(g => {
      const el = this.querySelector(`#gear-${g}`);
      if (gear.includes(g)) el.classList.add('active');
      else el.classList.remove('active');
    });

    // =======================================================
    // XỬ LÝ TỐC ĐỘ NỔI BẬT 
    // =======================================================
    const speedEl = this.querySelector('#vf-speed-container');
    const numericSpeed = Math.round(Number(speed));
    
    // Nếu đang đỗ hoặc tốc độ = 0 thì ẩn đồng hồ, nhường chỗ cho Cần số
    if (gear.includes('P') || numericSpeed === 0) {
      speedEl.style.display = 'none';
    } else {
      speedEl.style.display = 'flex';
      this.querySelector('#vf-speed').innerText = numericSpeed;
    }

    // =======================================================
    // XỬ LÝ BẢN ĐỒ CHỐNG NHẤP NHÁY (ANTI-FLICKER)
    // =======================================================
    const tracker = hass.states[`device_tracker.${p}_vi_tri_gps`];
    const lat = tracker?.attributes?.latitude;
    const lon = tracker?.attributes?.longitude;
    const mapStage = this.querySelector('#vf-map-stage');

    if (lat && lon) {
      // Làm tròn tọa độ tới 4 chữ số thập phân (sai số khoảng 11 mét)
      // Việc này giúp bỏ qua những rung lắc nhỏ của vệ tinh khi xe đang đỗ
      const roundedLat = Math.round(lat * 10000) / 10000;
      const roundedLon = Math.round(lon * 10000) / 10000;

      // Chỉ nạp lại iFrame nếu xe THỰC SỰ ĐÃ DI CHUYỂN ra khỏi vùng 11m
      if (this._lastLat !== roundedLat || this._lastLon !== roundedLon) {
        this._lastLat = roundedLat;
        this._lastLon = roundedLon;
        const bbox = `${lon - 0.005},${lat - 0.005},${lon + 0.005},${lat + 0.005}`;
        const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;
        mapStage.innerHTML = `<iframe src="${mapUrl}" class="vf-map-iframe"></iframe>`;
      }
    }

    // Cảnh báo
    const warnContainer = this.querySelector('#vf-warnings');
    if (warnings.length > 0) {
      warnContainer.innerHTML = warnings.map(w => `<div class="vf-warning-badge"><ha-icon icon="mdi:alert-circle-outline" style="--mdc-icon-size: 14px;"></ha-icon> ${w}</div>`).join('');
    } else {
      warnContainer.innerHTML = `<div class="vf-safe-badge"><ha-icon icon="mdi:check-circle-outline" style="--mdc-icon-size: 14px;"></ha-icon> Hệ thống an toàn</div>`;
    }
  }

  getCardSize() { return 6; }
}

customElements.define('vinfast-digital-twin', VinFastDigitalTwin);
