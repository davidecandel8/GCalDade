from datetime import datetime

class FitFetcher:
    def __init__(self, service):
        self.service = service

    def fetch_aggregate(self, start_ms, end_ms, request_body):
        request_body['startTimeMillis'] = start_ms
        request_body['endTimeMillis'] = end_ms
        try:
            return self.service.users().dataset().aggregate(userId='me', body=request_body).execute()
        except Exception:
            return {}

    def fetch_raw_sessions(self, start_ms, end_ms):
        """Scarica e NORMALIZZA le sessioni (fix del crash end_ms)"""
        try:
            response = self.service.users().sessions().list(
                userId='me', 
                startTime=datetime.fromtimestamp(start_ms/1000).isoformat() + 'Z',
                endTime=datetime.fromtimestamp(end_ms/1000).isoformat() + 'Z',
                includeDeleted=False
            ).execute()
            
            raw_list = response.get('session', [])
            cleaned_list = []
            
            for s in raw_list:
                # Normalizzazione immediata dei dati
                start = int(s.get('startTimeMillis', 0))
                end = int(s.get('endTimeMillis', 0))
                cleaned_list.append({
                    "name": s.get('name', 'Activity'),
                    "activity_type": int(s.get('activityType', 0)),
                    "start_ms": start,
                    "end_ms": end,
                    "start_fmt": datetime.fromtimestamp(start/1000).strftime('%H:%M'),
                    "end_fmt": datetime.fromtimestamp(end/1000).strftime('%H:%M'),
                    "duration": (end - start) / 60000 # minuti
                })
            return cleaned_list
        except Exception as e: 
            print(f"⚠️ Session Fetch Error: {e}")
            return []

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
                    return d['point'][-1]['value']
        except: pass
        return None

    def find_step_source(self):
        try:
            response = self.service.users().dataSources().list(userId='me', dataTypeName='com.google.step_count.delta').execute()
            # 1. Cerca Watch Samsung Derivato (Migliore)
            for ds in response.get('dataSource', []):
                if "SM-R9" in ds.get('device', {}).get('model', '') and "derived" in ds.get('type', ''):
                    return ds.get('dataStreamId')
            # 2. Cerca Watch Samsung Raw (Fallback)
            for ds in response.get('dataSource', []):
                if "SM-R9" in ds.get('device', {}).get('model', ''):
                    return ds.get('dataStreamId')
            # 3. Merged
            return "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas"
        except: return "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas"