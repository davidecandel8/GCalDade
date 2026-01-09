# modules/fit/processors.py

class FitProcessor:
    @staticmethod
    def extract_int(dataset_item):
        points = dataset_item.get('point', [])
        return int(sum(v['intVal'] for x in points for v in x['value'] if 'intVal' in v)) if points else 0

    @staticmethod
    def extract_float(dataset_item):
        points = dataset_item.get('point', [])
        vals = [v['fpVal'] for x in points for v in x['value'] if 'fpVal' in v]
        return vals[-1] if vals else 0.0

    @staticmethod
    def calculate_active_hr(hr_samples, resting_hr):
        if not hr_samples: return None
        threshold = (resting_hr + 10) if resting_hr else 65
        active = [s['bpm'] for s in hr_samples if s['bpm'] > threshold]
        return int(sum(active)/len(active)) if active else None

    @staticmethod
    def calculate_sleep_rhr(hr_samples, sleep_data):
        if not sleep_data or not hr_samples: return None
        try:
            def to_mins(t): h, m = map(int, t.split(':')); return h*60+m
            s_start = to_mins(sleep_data['start']); s_end = to_mins(sleep_data['end'])
            vals = []
            for s in hr_samples:
                t = to_mins(s['time'])
                if (s_start > s_end and (t >= s_start or t <= s_end)) or (s_start <= t <= s_end):
                    vals.append(s['bpm'])
            return int(sum(vals)/len(vals)) if vals else None
        except: return None

    @staticmethod
    def calculate_energy_score(sleep, steps, rhr):
        score = 0
        if sleep.get('total_hours',0) >= 7: score += 40
        if rhr and rhr < 60: score += 30
        if steps > 8000: score += 30
        return min(100, score)