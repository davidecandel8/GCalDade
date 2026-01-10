from datetime import datetime

class FitProcessor:
    @staticmethod
    def extract_int(dataset_item):
        points = dataset_item.get('point', [])
        return int(sum(v['intVal'] for x in points for v in x['value'] if 'intVal' in v))

    @staticmethod
    def extract_float(dataset_item):
        points = dataset_item.get('point', [])
        return sum(v['fpVal'] for x in points for v in x['value'] if 'fpVal' in v)

    @staticmethod
    def _is_time_in_range(time_str, start_str, end_str):
        """Helper per verificare se un orario HH:MM è dentro un range (gestisce accavallamento notte)."""
        def to_mins(t): 
            h, m = map(int, t.split(':'))
            return h * 60 + m
        
        t = to_mins(time_str)
        s = to_mins(start_str)
        e = to_mins(end_str)

        if s > e: # Scavalla la mezzanotte (es. 23:00 -> 07:00)
            return t >= s or t <= e
        else:     # Stesso giorno (es. 14:00 -> 16:00)
            return s <= t <= e

    def calculate_active_hr(self, hr_samples, sleep_data):
        """Calcola la media HR escludendo ESPLICITAMENTE gli orari di sonno."""
        if not hr_samples: return None
        
        # Se non c'è sonno, tutto è "active"
        if not sleep_data or sleep_data.get('total_hours', 0) == 0:
            avg = sum(s['bpm'] for s in hr_samples) / len(hr_samples)
            return int(avg)

        active_vals = []
        for sample in hr_samples:
            # Se NON è nel range del sonno, è attivo
            if not self._is_time_in_range(sample['time'], sleep_data['start'], sleep_data['end']):
                active_vals.append(sample['bpm'])
        
        return int(sum(active_vals)/len(active_vals)) if active_vals else None

    def calculate_sleep_rhr(self, hr_samples, sleep_data):
        """Calcola la media HR includendo SOLO gli orari di sonno."""
        if not sleep_data or sleep_data.get('total_hours', 0) == 0 or not hr_samples: 
            return None
            
        sleep_vals = []
        for sample in hr_samples:
            if self._is_time_in_range(sample['time'], sleep_data['start'], sleep_data['end']):
                sleep_vals.append(sample['bpm'])
                
        return int(sum(sleep_vals)/len(sleep_vals)) if sleep_vals else None

    @staticmethod
    def calculate_energy_score(sleep, steps, rhr):
        score = 0
        # FIX: Usa total_hours (calcolato nel service come helper) o converti total_minutes
        hours = sleep.get('total_hours', 0) 
        # Oppure se sleep ha solo minuti: hours = sleep.get('total_minutes', 0) / 60
        
        if hours >= 7: score += 40
        if rhr and rhr < 60: score += 30
        if steps > 8000: score += 30
        return min(100, score)