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
        
        # Body & Medical
        body = self._get_body_stats_robust(start_ms, end_ms)
        medical = self._get_medical_stats_robust(start_ms, end_ms) 
        
        # Vitali
        vitals = self._get_vitals(start_ms, end_ms)
        
        # Sonno (Cerca 14h indietro)
        sleep_start_search = start_ms - (14 * 60 * 60 * 1000) 
        sleep = self._get_sleep(sleep_start_search, end_ms)
        
        sport = self._get_sport(start_ms, end_ms)
        nutrition = self._get_nutrition(start_ms, end_ms)

        # 2. CALCOLI
        rhr = self._resolve_rhr(start_ms, end_ms, vitals, sleep)
        act_hr = self.processor.calculate_active_hr(vitals['hr_samples'], rhr)
        en_score = self.processor.calculate_energy_score(sleep, core['steps'], rhr)

        # 3. PAYLOAD (INT FORCING ATTIVO)
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
            "health_body_fat_perc": body['fat'],
            "health_muscle_mass_kg": body['muscle'],
            "health_bmr_kcal": int(body['bmr']) if body['bmr'] else None,
            "health_body_water_perc": body['water'],

            "health_avg_hr": vitals['avg_hr'],
            "health_resting_hr": rhr,
            "health_active_hr": act_hr,
            "health_min_hr": vitals['min_hr'],
            "health_max_hr": vitals['max_hr'],
            "health_avg_spo2": vitals['avg_spo2'],

            "health_blood_pressure_sys": medical['sys'],
            "health_blood_pressure_dia": medical['dia'],
            "health_blood_glucose_avg": medical['glucose'],
            "health_body_temp_avg": medical['temp'],

            "health_sleep_hours_total": sleep['total_hours'],
            "health_sleep_score": sleep['efficiency_score'],
            "health_energy_score": en_score,
            
            "health_calories_intake": int(nutrition['calories']),
            "health_water_ml": int(nutrition['water']),

            "raw_data": {
                "fit_aggregates_dump": core,
                "sleep_detailed": sleep,
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
        # Fetch Latest Data Point
        w_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.weight")
        fat_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.body.fat.percentage")
        bmr_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.calories.bmr")
        lean_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.body.lean_body_mass")
        water_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.body.water_mass") # Raro in HC
        
        weight = w_raw[0].get('fpVal') if w_raw else None
        
        # Acqua: Se non c'è il dato raw, lo stimiamo dal peso (es. 60% uomo adulto) se vuoi,
        # ma meglio lasciarlo None se manca il sensore.
        water_perc = None
        if water_raw and weight:
             water_perc = round((water_raw[0].get('fpVal') / weight) * 100, 2)

        return {
            "weight": weight,
            "fat": fat_raw[0].get('fpVal') if fat_raw else None,
            "bmr": bmr_raw[0].get('fpVal') if bmr_raw else None,
            "muscle": lean_raw[0].get('fpVal') if lean_raw else None,
            "water": water_perc
        }

    def _get_sleep(self, s, e):
        # Fetcher ora ritorna oggetti puliti con chiavi 'start_ms', 'end_ms'
        sessions = self.fetcher.fetch_raw_sessions(s, e)
        sleeps = [x for x in sessions if x['activity_type'] == 72]
        
        if not sleeps: 
            return {"total_hours": 0.0, "efficiency_score": 0}
        
        # Ora possiamo usare end_ms in sicurezza
        main = max(sleeps, key=lambda x: x['end_ms'] - x['start_ms'])
        
        # Fetch stages
        body = {"aggregateBy": [{"dataTypeName": "com.google.sleep.segment"}], "startTimeMillis": main['start_ms'], "endTimeMillis": main['end_ms']}
        r = self.fetcher.fetch_aggregate(0,0,body)
        
        stages = {"awake": 0, "sleep": 0, "out_of_bed": 0, "light": 0, "deep": 0, "rem": 0}
        if r.get('bucket') and r['bucket'][0].get('dataset'):
            for p in r['bucket'][0]['dataset'][0].get('point', []):
                dur = (int(p.get('endTimeNanos',0)) - int(p.get('startTimeNanos',0)))/1e9/60
                t = p['value'][0]['intVal']
                if t==1: stages['awake']+=dur
                elif t==2: stages['sleep']+=dur
                elif t==4: stages['light']+=dur
                elif t==5: stages['deep']+=dur
                elif t==6: stages['rem']+=dur

        tot = stages['light']+stages['deep']+stages['rem']+stages['sleep']
        eff = int(tot/(tot+stages['awake'])*100) if tot > 0 else 0
        
        return {
            "total_hours": round(tot/60, 2), 
            "stages_min": stages, 
            "efficiency_score": eff, 
            "start": main['start_fmt'], 
            "end": main['end_fmt']
        }

    def _get_sport(self, s, e):
        # Fetcher ritorna già oggetti puliti
        sessions = self.fetcher.fetch_raw_sessions(s, e)
        res = []
        for sess in sessions:
            if sess['activity_type'] != 72:
                # Mappatura nomi
                name = self.ACTIVITY_MAP.get(sess['activity_type'], f"Sport {sess['activity_type']}")
                res.append({"name": name, "duration": sess['duration'], "start_fmt": sess['start_fmt']})
        return res

    # ... Metodi medical, nutrition, vitals, resolve_rhr UGUALI a prima ...
    # Assicurati di includerli!
    def _get_medical_stats_robust(self, s, e):
        bp_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.blood_pressure")
        sys = None; dia = None
        if bp_raw and len(bp_raw) >= 2: sys=bp_raw[0].get('fpVal'); dia=bp_raw[1].get('fpVal')
        gluc_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.blood_glucose")
        temp_raw = self.fetcher.fetch_latest_data_point(s, e, "com.google.body.temperature")
        return {"sys": sys, "dia": dia, "glucose": gluc_raw[0].get('fpVal') if gluc_raw else None, "temp": temp_raw[0].get('fpVal') if temp_raw else None}

    def _get_vitals(self, s, e):
        body = {"aggregateBy": [{"dataTypeName": "com.google.heart_rate.bpm"}, {"dataTypeName": "com.google.oxygen_saturation"}], "bucketByTime": {"durationMillis": 300000}}
        r = self.fetcher.fetch_aggregate(s, e, body)
        hr_samples = []; spo2_samples = []
        for b in r.get('bucket', []):
            t = datetime.fromtimestamp(int(b['startTimeMillis'])/1000).strftime('%H:%M')
            d = b['dataset']
            if d[0].get('point'): hr_samples.append({"time": t, "bpm": int(d[0]['point'][0]['value'][0]['fpVal'])})
            if d[1].get('point'): spo2_samples.append({"time": t, "val": float(d[1]['point'][0]['value'][0]['fpVal'])})
        return {"hr_samples": hr_samples, "avg_hr": int(sum(x['bpm'] for x in hr_samples)/len(hr_samples)) if hr_samples else None, "avg_spo2": int(sum(x['val'] for x in spo2_samples)/len(spo2_samples)) if spo2_samples else None, "min_hr": min([x['bpm'] for x in hr_samples]) if hr_samples else None, "max_hr": max([x['bpm'] for x in hr_samples]) if hr_samples else None, "vo2_max": None}

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
             w_val = d_nut[1]['point'][0]['value']
             water = w_val[0]['fpVal'] * 1000 if w_val else 0
        return {"calories": cal, "water": water}

    def _resolve_rhr(self, s, e, vitals, sleep):
        body = {"aggregateBy": [{"dataTypeName": "com.google.heart_rate.resting"}]}
        r = self.fetcher.fetch_aggregate(s, e, body)
        d = r.get('bucket', [{}])[0].get('dataset', [])
        if d and d[0].get('point'): return int(d[0]['point'][0]['value'][0]['fpVal'])
        val = self.processor.calculate_sleep_rhr(vitals['hr_samples'], sleep)
        if val: return val
        return vitals['min_hr']