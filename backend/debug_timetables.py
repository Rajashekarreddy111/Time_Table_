import os
from storage.memory_store import store

print('MongoDB available:', store._mongo_available)
records = store.list_timetables()
print(f'Total timetables: {len(records)}')

if records:
    for i, record in enumerate(records[:2]):
        print(f'\nRecord {i+1}:')
        print(f'  ID: {record.get("id")}')
        print(f'  Year: {record.get("year")}')
        print(f'  Section: {record.get("section")}')
        print(f'  Has valid timetable: {record.get("hasValidTimetable")}')
        print(f'  Keys: {list(record.keys())}')
        if 'allGrids' in record:
            print(f'  allGrids sections: {list(record["allGrids"].keys())}')
        if 'grid' in record:
            print(f'  Has single grid: True')
else:
    print('No timetables found in database.')