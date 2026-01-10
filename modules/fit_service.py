from datetime import datetime
import pytz
from modules.fit.fetchers import FitFetcher
from modules.fit.processors import FitProcessor

class GoogleFitService:
    def __init__(self, service):
        self.fetcher = FitFetcher(service)
        self.processor = FitProcessor()
        
        self.ACTIVITY_MAP = {
            7: "Camminata", 8: "Corsa", 9: "Aerobica", 
            28: "Calcio", 88: "Calcio", 30: "Calcio", 
            58: "Trekking", 72: "Sonno", 97: "Palestra"
        }

    def get_full_day_metrics(self, target_date=None):
        tz = pytz.timezone('Europe/Rome')
        if target_date is None: target_date = datetime.now(tz)
        
        if target_date.tzinfo is None: target_date = tz.localize(target_date)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_window = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        start_ms = int(start_of_day.timestamp() * 1000)
        end_ms = int(end_of_window.timestamp() * 1000)

        # 1. FETCH
        watch_id = self.fetcher.find_step_source()
        core = self._get_core_stats(start_ms, end_ms, watch_id)
        
        body = self._get_body_stats_robust(start_ms, end_ms)
        medical = self._get_medical_stats_robust(start_ms, end_ms) 
        vitals = self._get_vitals(start_ms, end_ms)
        
        # Sonno (14h lookback)
        sleep_start_search = start_ms - (14 * 60 * 60 * 1000) 
        sleep = self._get_sleep(sleep_start_search, end_ms)
        
        # Vitali Notturni
        night_start = sleep_start_search if sleep['total_minutes'] > 0 else start_ms
        night_vitals = self._get_night_vitals(night_start, end_ms)

        sport = self._get_sport(start_ms, end_ms)
        nutrition = self._get_nutrition(start_ms, end_ms)

        # 2. CALCOLI
        rhr = self._resolve_rhr(start_ms, end_ms, vitals, sleep)
        act_hr = self.processor.calculate_active_hr(vitals['hr_samples'], sleep)
        
        sleep_hours_for_calc = sleep['total_minutes'] / 60.0
        en_score = self.processor.calculate_energy_score({"total_hours": sleep_hours_for_calc}, core['steps'], rhr)

        # 3. PAYLOAD
        return {
            "health_steps": int(core['steps']),
            "health_distance_m": int(core['distance']),
            "health_floors_climbed": int(core['floors']),
            "health_active_minutes": int(core['active_minutes']),
            "health_cardio_points": int(core['cardio_points']),
            "health_calories_burnt": int(core['calories']),
            "health_power_avg_watts": core['watts'],
            "health_vo2_max": vitals['vo2_max'],

            "health_weight_kg": body['weight'],
            "health_bmi": body['bmi'], 
            "health_body_fat_perc": body['fat_perc'],
            "health_body_fat_kg": body['fat_kg'],
            "health_muscle_mass_kg": body['muscle'],
            "health_bmr_kcal": body['bmr'],
            "health_body_water_perc": body['water_perc'],
            "health_body_water_kg": body['water_kg'],

            "health_avg_hr": vitals['avg_hr'],
            "health_resting_hr": rhr,
            "health_active_hr": act_hr,
            "health_min_hr": vitals['min_hr'],
            "health_max_hr": vitals['max_hr'],
            "health_avg_spo2": vitals['avg_spo2'],

            "health_blood_pressure_sys": medical['sys'],
            "health_blood_pressure_dia": medical['dia'],
            "health_blood_glucose_avg": medical['glucose'],
            
            # Vitali Notturni
            "health_skin_temp_avg": night_vitals['skin_temp'],
            "health_respiratory_rate_avg": night_vitals['resp_rate'],

            # Sonno Dettagliato
            "health_sleep_minutes": sleep['total_minutes'],
            "health_sleep_awake_minutes": int(sleep['stages_min']['awake']),
            "health_sleep_light_minutes": int(sleep['stages_min']['light']),
            "health_sleep_deep_minutes": int(sleep['stages_min']['deep']),
            "health_sleep_rem_minutes": int(sleep['stages_min']['rem']),
            "health_sleep_score": sleep['efficiency_score'],
            "health_energy_score": en_score,
            
            "health_calories_intake": int(nutrition['calories']),
            "health_water_ml": int(nutrition['water']),

            "raw_data": {
                "fit_aggregates_dump": core,
                "sleep_detailed": sleep,
                "night_vitals_raw": night_vitals,
                "sport_activities": sport,
                "heart_rate_samples": vitals['hr_samples'],
                "step_source_used": watch_id,
                "last_sync": datetime.now(tz).isoformat()
            }
        }

    # --- HELPERS ---

    def _get_core_stats(self, s, e, watch_id):
        body_main = {
            "aggregateBy": [
                {"dataTypeName": "com.google.step_count.delta"}, 
                {"dataTypeName": "com.google.step_count.delta", "dataSourceId": watch_id},
                {"dataTypeName": "com.google.distance.delta"},
                {"dataTypeName": "com.google.calories.expended"},
                {"dataTypeName": "com.google.heart_minutes"},
                {"dataTypeName": "com.google.active_minutes"}
            ]
        }
        r_main = self.fetcher.fetch_aggregate(s, e, body_main)
        r_floor = self.fetcher.fetch_aggregate(s, e, {"aggregateBy": [{"dataTypeName": "com.google.floor_change"}]})
        r_power = self.fetcher.fetch_aggregate(s, e, {"aggregateBy": [{"dataTypeName": "com.google.power.sample"}]})

        d_main = r_main.get('bucket', [{}])[0].get('dataset', [])
        d_floor = r_floor.get('bucket', [{}])[0].get('dataset', [])
        d_power = r_power.get('bucket', [{}])[0].get('dataset', [])

        steps = 0
        if d_main:
            s1 = self.processor.extract_int(d_main[0])
            s2 = self.processor.extract_int(d_main[1])
            steps = max(s1, s2)
        
        return {
            "steps": steps,
            "distance": self.processor.extract_float(d_main[2]) if d_main else 0.0,
            "calories": self.processor.extract_float(d_main[3]) if d_main else 0.0,
            "cardio_points": self.processor.extract_float(d_main[4]) if d_main else 0.0,
            "active_minutes": self.processor.extract_int(d_main[5]) if d_main else 0,
            "floors": self.processor.extract_float(d_floor[0]) if d_floor else 0,
            "watts": self.processor.extract_float(d_power[0]) if d_power else None
        }

    def _get_body_stats_robust(self, s, e):
        ms_in_30_days = 30 * 24 * 60 * 60 * 1000
        search_s = s - ms_in_30_days
        
        w_raw = self.fetcher.fetch_latest_data_point(search_s, e, "com.google.weight")
        fat_raw = self.fetcher.fetch_latest_data_point(search_s, e, "com.google.body.fat.percentage")
        h_raw = self.fetcher.fetch_latest_data_point(search_s, e, "com.google.height")
        water_mass_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.body.water_mass")

        weight = w_raw[0].get('fpVal') if w_raw else None
        fat_perc = fat_raw[0].get('fpVal') if fat_raw else None
        height_m = h_raw[0].get('fpVal') if h_raw else 1.75 
        
        bmr = None; muscle_smm = None; water_perc = None; water_kg = None; fat_kg = None; bmi = None

        if weight:
            if height_m: bmi = round(weight / (height_m * height_m), 1)
            
            height_cm = height_m * 100; age = 24 
            bmr = int((10 * weight) + (6.25 * height_cm) - (5 * age) + 5)

            lean_mass_kg = None
            if fat_perc:
                fat_kg = round(weight * (fat_perc / 100), 2)
                lean_mass_kg = weight - fat_kg
                muscle_smm = round(lean_mass_kg * 0.54, 2)

            if water_mass_raw:
                water_kg = round(water_mass_raw[0].get('fpVal'), 2)
                water_perc = round((water_kg / weight) * 100, 2)
            elif lean_mass_kg:
                water_kg = round(lean_mass_kg * 0.73, 2)
                water_perc = round((water_kg / weight) * 100, 2)

        return {
            "weight": weight, "bmi": bmi, "fat_perc": fat_perc, "fat_kg": fat_kg,
            "muscle": muscle_smm, "bmr": bmr, "water_perc": water_perc, "water_kg": water_kg
        }

    def _get_sleep(self, s, e):
        sessions = self.fetcher.fetch_raw_sessions(s, e)
        sleeps = [x for x in sessions if x['activity_type'] == 72]
        
        if not sleeps: 
            return {
                "total_minutes": 0, "efficiency_score": 0, "start": "00:00", "end": "00:00", 
                "stages_min": {"awake": 0, "sleep": 0, "out_of_bed": 0, "light": 0, "deep": 0, "rem": 0}
            }
        
        main_sleep = max(sleeps, key=lambda x: x['duration'])
        
        total_minutes_accumulated = 0
        total_stages = {"awake": 0, "sleep": 0, "out_of_bed": 0, "light": 0, "deep": 0, "rem": 0}
        
        for sess in sleeps:
            body = {"aggregateBy": [{"dataTypeName": "com.google.sleep.segment"}], "startTimeMillis": sess['start_ms'], "endTimeMillis": sess['end_ms']}
            
            # BUG FIX: Qui prima passavo (0,0,body), ora passo i tempi corretti della sessione!
            r = self.fetcher.fetch_aggregate(sess['start_ms'], sess['end_ms'], body)
            
            sess_minutes = 0
            has_details = False
            
            if r.get('bucket') and r['bucket'][0].get('dataset'):
                points = r['bucket'][0]['dataset'][0].get('point', [])
                if points:
                    has_details = True
                    for p in points:
                        dur = (int(p.get('endTimeNanos',0)) - int(p.get('startTimeNanos',0)))/1e9/60
                        t = p['value'][0]['intVal']
                        if t==1: total_stages['awake']+=dur
                        elif t==2: 
                            total_stages['sleep']+=dur
                            sess_minutes+=dur
                        elif t==4: 
                            total_stages['light']+=dur
                            sess_minutes+=dur
                        elif t==5: 
                            total_stages['deep']+=dur
                            sess_minutes+=dur
                        elif t==6: 
                            total_stages['rem']+=dur
                            sess_minutes+=dur

            if not has_details:
                sess_minutes = sess['duration']
            
            total_minutes_accumulated += sess_minutes

        eff_denom = total_minutes_accumulated + total_stages['awake']
        efficiency = int((total_minutes_accumulated / eff_denom) * 100) if eff_denom > 0 else 0

        return {
            "total_minutes": int(total_minutes_accumulated),
            "stages_min": total_stages, 
            "efficiency_score": efficiency, 
            "start": main_sleep['start_fmt'], 
            "end": main_sleep['end_fmt']
        }

    def _get_night_vitals(self, s, e):
        body = {
            "aggregateBy": [
                {"dataTypeName": "com.google.body.temperature"}, 
                {"dataTypeName": "com.google.respiratory_rate"} 
            ],
            "bucketByTime": {"durationMillis": e - s},
            "startTimeMillis": s, "endTimeMillis": e
        }
        
        skin_temp_avg = None
        resp_rate_avg = None

        try:
            r = self.fetcher.fetch_aggregate(s, e, body)
            if r.get('bucket'):
                ds = r['bucket'][0].get('dataset', [])
                
                # Check Debug se i dati ci sono ma sono vuoti
                # print(f"DEBUG NIGHT VITALS: {ds}") 
                
                # Temp
                if len(ds) > 0 and ds[0].get('point'):
                    vals = [p['value'][0]['fpVal'] for p in ds[0]['point']]
                    if vals: skin_temp_avg = round(sum(vals)/len(vals), 2)
                
                # Resp Rate
                if len(ds) > 1 and ds[1].get('point'):
                    vals = [p['value'][0]['fpVal'] for p in ds[1]['point']]
                    if vals: resp_rate_avg = round(sum(vals)/len(vals), 1)
                    
        except Exception as ex:
            print(f"   [WARN] Night Vitals Error (Check Permissions!): {ex}")

        return {"skin_temp": skin_temp_avg, "resp_rate": resp_rate_avg}

    def _get_sport(self, s, e):
        sessions = self.fetcher.fetch_raw_sessions(s, e)
        res = []
        for sess in sessions:
            if sess['activity_type'] != 72:
                name = self.ACTIVITY_MAP.get(sess['activity_type'], f"Sport {sess['activity_type']}")
                res.append({"name": name, "duration": sess['duration'], "start_fmt": sess['start_fmt']})
        return res

    def _get_medical_stats_robust(self, s, e):
        bp_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.blood_pressure")
        sys = None; dia = None
        if bp_raw and len(bp_raw) >= 2: sys=bp_raw[0].get('fpVal'); dia=bp_raw[1].get('fpVal')
        gluc_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.blood_glucose")
        
        return {"sys": sys, "dia": dia, "glucose": gluc_raw[0].get('fpVal') if gluc_raw else None}

    def _get_vitals(self, s, e):
        body = {"aggregateBy": [{"dataTypeName": "com.google.heart_rate.bpm"}, {"dataTypeName": "com.google.oxygen_saturation"}], "bucketByTime": {"durationMillis": 300000}}
        r = self.fetcher.fetch_aggregate(s, e, body)
        hr_samples = []; spo2_samples = []
        for b in r.get('bucket', []):
            st = int(b['startTimeMillis'])
            t_fmt = datetime.fromtimestamp(st/1000).strftime('%H:%M')
            d = b['dataset']
            if d[0].get('point'): hr_samples.append({"time": t_fmt, "bpm": int(d[0]['point'][0]['value'][0]['fpVal'])})
            if d[1].get('point'): spo2_samples.append({"time": t_fmt, "val": float(d[1]['point'][0]['value'][0]['fpVal'])})
        return {
            "hr_samples": hr_samples, 
            "avg_hr": int(sum(x['bpm'] for x in hr_samples)/len(hr_samples)) if hr_samples else None, 
            "avg_spo2": int(sum(x['val'] for x in spo2_samples)/len(spo2_samples)) if spo2_samples else None, 
            "min_hr": min([x['bpm'] for x in hr_samples]) if hr_samples else None, 
            "max_hr": max([x['bpm'] for x in hr_samples]) if hr_samples else None, 
            "vo2_max": None
        }

    def _get_nutrition(self, s, e):
        body = {"aggregateBy": [{"dataTypeName": "com.google.nutrition"}, {"dataTypeName": "com.google.hydration"}]}
        r = self.fetcher.fetch_aggregate(s, e, body)
        cal = 0
        d_nut = r.get('bucket', [{}])[0].get('dataset', [{}, {}])
        if d_nut[0].get('point'):
            for p in d_nut[0]['point']:
                for v in p['value']:
                    if 'mapVal' in v:
                        for item in v['mapVal']:
                            if item['key'] == 'calories': cal += item['value']['fpVal']
        water = 0
        if len(d_nut) > 1 and d_nut[1].get('point'):
             for p in d_nut[1]['point']:
                 if p.get('value'):
                     water += p['value'][0]['fpVal'] * 1000
        return {"calories": cal, "water": int(water)}

    def _resolve_rhr(self, s, e, vitals, sleep):
        body = {"aggregateBy": [{"dataTypeName": "com.google.heart_rate.resting"}]}
        r = self.fetcher.fetch_aggregate(s, e, body)
        d = r.get('bucket', [{}])[0].get('dataset', [])
        if d and d[0].get('point'): return int(d[0]['point'][0]['value'][0]['fpVal'])
        val = self.processor.calculate_sleep_rhr(vitals['hr_samples'], sleep)
        if val: return val
        return vitals['min_hr']