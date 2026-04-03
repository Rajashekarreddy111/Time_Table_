import requests, zipfile, io

url = 'http://127.0.0.1:8000/timetables/all-sections-workbook'
print('Calling:', url)
try:
    resp = requests.get(url, timeout=15)
    print('status', resp.status_code)
    print('content-type', resp.headers.get('content-type'))
    print('content-disposition', resp.headers.get('content-disposition'))
    print('len', len(resp.content))
    try:
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        print('zip contents', z.namelist()[:10])
        print('zip OK')
    except Exception as e:
        print('zip error', repr(e))
except Exception as e:
    print('request failed', repr(e))
