# modules/fit/processors.py

class FitProcessor:
    @staticmethod
    def extract_float(dataset_item):
        points = dataset_item.get('point', [])
        return sum(v['fpVal'] for x in points for v in x['value'] if 'fpVal' in v)

    @staticmethod
    def extract_int(dataset_item):
        points = dataset_item.get('point', [])
        return int(sum(v['intVal'] for x in points for v in x['value'] if 'intVal' in v))

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
            def to_mins(t): 
                parts = t.split(':')
                return int(parts[0])*60 + int(parts[1])
            
            s_start = to_mins(sleep_data['start'])
            s_end = to_mins(sleep_data['end'])
            vals = []
            
            # Gestione cross-day (es. dormo dalle 23:00 alle 07:00)
            cross_day = s_start > s_end 

            for s in hr_samples:
                t = to_mins(s['time'])
                in_sleep = False
                if cross_day:
                    if t >= s_start or t <= s_end: in_sleep = True
                else:
                    if s_start <= t <= s_end: in_sleep = True
                
                if in_sleep: vals.append(s['bpm'])
                
            return int(sum(vals)/len(vals)) if vals else None
        except Exception as e: 
            print(f"Error calulating RHR: {e}")
            return None
        
    @staticmethod
    def calculate_energy_score(sleep, steps, rhr):
        score = 0
        # Sleep contribution
        if sleep:
            duration = sleep.get('duration_minutes', 0)
            if duration >= 420: score += 40
            elif duration >= 360: score += 30
            elif duration >= 300: score += 20
            else: score += 10
        
        # Steps contribution
        if steps:
            if steps >= 10000: score += 40
            elif steps >= 7500: score += 30
            elif steps >= 5000: score += 20
            else: score += 10
        
        # RHR contribution
        if rhr:
            if rhr <= 60: score += 20
            elif rhr <= 70: score += 15
            elif rhr <= 80: score += 10
            else: score += 5
        
        return score