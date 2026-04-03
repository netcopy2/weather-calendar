import os
import requests
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar, Event

# --- [설정] ---
NX, NY = 60, 127
REG_ID_TEMP = '11B10101'  # 서울 기온 구역
REG_ID_LAND = '11B00000'  # 서울/경인 육상 구역
API_KEY = os.environ.get('KMA_API_KEY')

def get_emoji(wf_or_sky, pty='0'):
    wf = str(wf_or_sky)
    if '비' in wf or '소나기' in wf: return "🌧️"
    if '눈' in wf: return "🌨️"
    if '구름많음' in wf: return "⛅"
    if '흐림' in wf: return "☁️"
    if '맑음' in wf or wf == '1': return "☀️"
    if pty != '0' and pty != '0': return "🌧️"
    if wf == '3': return "⛅"
    if wf == '4': return "☁️"
    return "☀️"

def fetch_api(url):
    try:
        res = requests.get(url)
        if res.status_code == 200: return res.json()
    except: return None
    return None

def main():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    cal = Calendar()
    cal.add('prodid', '-//KMA Weather Calendar//mxm.dk//')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', '기상청 날씨')
    cal.add('X-WR-TIMEZONE', 'Asia/Seoul')

    # 1. 단기예보 (0~3일)
    base_date = now.strftime('%Y%m%d')
    base_time = f"{max([h for h in [2, 5, 8, 11, 14, 17, 20, 23] if h <= now.hour], default=2):02d}00"
    url_short = f"https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst?dataType=JSON&base_date={base_date}&base_time={base_time}&nx={NX}&ny={NY}&authKey={API_KEY}"
    
    forecast_map = {}
    short_res = fetch_api(url_short)
    if short_res and 'response' in short_res and 'body' in short_res['response']:
        items = short_res['response']['body']['items']['item']
        for it in items:
            d, t, cat, val = it['fcstDate'], it['fcstTime'], it['category'], it['fcstValue']
            if d not in forecast_map: forecast_map[d] = {}
            if t not in forecast_map[d]: forecast_map[d][t] = {}
            forecast_map[d][t][cat] = val

    # 2. 중기예보 (4~10일)
    tm_fc = now.strftime('%Y%m%d') + ("0600" if now.hour < 18 else "1800")
    url_mid_temp = f"https://apihub.kma.go.kr/api/typ02/openApi/MidFcstInfoService/getMidTa?dataType=JSON&regId={REG_ID_TEMP}&tmFc={tm_fc}&authKey={API_KEY}"
    url_mid_land = f"https://apihub.kma.go.kr/api/typ02/openApi/MidFcstInfoService/getMidLandFcst?dataType=JSON&regId={REG_ID_LAND}&tmFc={tm_fc}&authKey={API_KEY}"
    
    mid_temp_res = fetch_api(url_mid_temp)
    mid_land_res = fetch_api(url_mid_land)
    mid_map = {}
    if mid_temp_res and mid_land_res:
        try:
            t_item = mid_temp_res['response']['body']['items']['item'][0]
            l_item = mid_land_res['response']['body']['items']['item'][0]
            for i in range(4, 11):
                d_str = (now + timedelta(days=i)).strftime('%Y%m%d')
                suffix = "Am" if i <= 7 else ""
                mid_map[d_str] = {
                    'min': t_item.get(f'taMin{i}'),
                    'max': t_item.get(f'taMax{i}'),
                    'wf': l_item.get(f'wf{i}{suffix}'),
                    'rn': l_item.get(f'rnSt{i}{suffix}')
                }
        except: pass

    # 3. 일정 생성
    for i in range(11):
        target_dt = now + timedelta(days=i)
        d_str = target_dt.strftime('%Y%m%d')
        event = Event()
        
        if d_str in forecast_map:
            d = forecast_map[d_str]
            times = sorted(d.keys())
            tmps = [float(d[t]['TMP']) for t in times if 'TMP' in d[t]]
            t_min, t_max = int(min(tmps)), int(max(tmps))
            rep_t = "1200" if "1200" in d else times[len(times)//2]
            rep_em = get_emoji(d[rep_t].get('SKY'), d[rep_t].get('PTY'))
            event.add('summary', f"{rep_em} {t_min}°/{t_max}°")
            desc = "\n".join([f"{t[:2]}시: {get_emoji(d[t].get('SKY'), d[t].get('PTY'))} {d[t].get('TMP')}°C" for t in times])
            event.add('description', desc)
        elif d_str in mid_map:
            m = mid_map[d_str]
            event.add('summary', f"{get_emoji(m['wf'])} {m['min']}°/{m['max']}°")
            event.add('description', f"날씨: {m['wf']}\n강수확률: {m['rn']}%")

        event.add('dtstart', target_dt.date())
        event.add('dtend', (target_dt + timedelta(days=1)).date())
        event.add('dtstamp', datetime.now())
        event.add('uid', f"{d_str}@kma_weather")
        cal.add_component(event)

    with open('weather.ics', 'wb') as f:
        f.write(cal.to_ical())
    print("✅ 모든 데이터 통합 완료!")

if __name__ == "__main__":
    main()
