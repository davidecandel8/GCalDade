from datetime import datetime, timezone

class FitFetcher:
    def __init__(self, service):
        self.service = service

    def fetch_aggregate(self, start_ms, end_ms, request_body):
        request_body['startTimeMillis'] = start_ms
        request_body['endTimeMillis'] = end_ms
        try:
            return self.service.users().dataset().aggregate(userId='me', body=request_body).execute()
        except Exception as e:
            # print(f"DEBUG: Aggreg Error {e}") # Scommenta se vuoi debuggare
            return {}

    def fetch_raw_sessions(self, start_ms, end_ms):
        try:
            # FIX DEPRECATION: Usa datetime.fromtimestamp(ts, timezone.utc)
            start_dt = datetime.fromtimestamp(start_ms/1000, timezone.utc).isoformat()
            end_dt = datetime.fromtimestamp(end_ms/1000, timezone.utc).isoformat()
            
            response = self.service.users().sessions().list(
                userId='me', 
                startTime=start_dt,
                endTime=end_dt,
                includeDeleted=False
            ).execute()
            
            raw_list = response.get('session', [])
            cleaned_list = []
            
            for s in raw_list:
                start = int(s.get('startTimeMillis', 0))
                end = int(s.get('endTimeMillis', 0))
                
                # Calcolo duration in minuti
                duration_min = (end - start) / 60000
                
                # Format time usando il fuso locale per leggibilità nel JSON finale, 
                # MA i calcoli interni usano i timestamp raw.
                # Nota: qui usiamo fromtimestamp "semplice" per avere l'ora locale (es. 23:00) per il report
                s_fmt = datetime.fromtimestamp(start/1000).strftime('%H:%M')
                e_fmt = datetime.fromtimestamp(end/1000).strftime('%H:%M')

                cleaned_list.append({
                    "name": s.get('name', 'Activity'),
                    "activity_type": int(s.get('activityType', 0)),
                    "start_ms": start,
                    "end_ms": end,
                    "start_fmt": s_fmt,
                    "end_fmt": e_fmt,
                    "duration": duration_min
                })
            
            return cleaned_list
        except Exception as e: 
            print(f"⚠️ Session Fetch Error: {e}")
            return []

    # ... (Il resto di fetch_latest_data_point e find_step_source rimane uguale)
    def fetch_latest_data_point(self, start_ms, end_ms, data_type_name):
        body = {
            "aggregateBy": [{"dataTypeName": data_type_name}],
            "bucketByTime": {"durationMillis": end_ms - start_ms},
            "startTimeMillis": start_ms, "endTimeMillis": end_ms
        }
        try:
            r = self.service.users().dataset().aggregate(userId='me', body=body).execute()
            if r.get('bucket') and r['bucket'][0].get('dataset'):
                d = r['bucket'][0]['dataset'][0]
                if d.get('point'):
                    return d['point'][-1]['value'] # Qui va bene l'ultimo punto (es. ultimo peso registrato)
        except: pass
        return None

    def find_step_source(self):
        try:
            response = self.service.users().dataSources().list(userId='me', dataTypeName='com.google.step_count.delta').execute()
            for ds in response.get('dataSource', []):
                if "SM-R9" in ds.get('device', {}).get('model', '') and "derived" in ds.get('type', ''):
                    return ds.get('dataStreamId')
            for ds in response.get('dataSource', []):
                if "SM-R9" in ds.get('device', {}).get('model', ''):
                    return ds.get('dataStreamId')
            return "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas"
        except: return "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas"