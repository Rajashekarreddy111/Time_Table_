import requests, zipfile, io

url = 'http://127.0.0.1:8000/timetables/all-sections-workbook'
print('Calling:', url)
resp = requests.get(url)
print('status', resp.status_code)
print('content-type', resp.headers.get('content-type'))
print('content-disposition', resp.headers.get('content-disposition'))

with open('tmp_All_Class_Timetables_Format.xlsx', 'wb') as f:
    f.write(resp.content)

print('bytes', len(resp.content))

try:
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    print('zip contents', z.namelist()[:10])
    print('zip OK')
except Exception as e:
    print('zip error', e)
