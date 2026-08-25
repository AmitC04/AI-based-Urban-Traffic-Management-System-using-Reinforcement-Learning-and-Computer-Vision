import requests
s = requests.Session()
s.post('http://127.0.0.1:5000/', data={'username':'traffic-admin', 'password':'admin123'})
print("stats:", s.get('http://127.0.0.1:5000/stats_api').text)
print("counts:", s.get('http://127.0.0.1:5000/live_counts').text)
