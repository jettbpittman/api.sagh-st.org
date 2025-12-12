import psycopg2
import json
import tabulate

with open("creds.json", "r") as f:
    creds = json.load(f)


con = psycopg2.connect(
        user=creds["database"]["username"],
        password=creds["database"]["password"],
        database=creds["database"]["database"],
        host=creds["database"]["host"],
        port="5432",
    )

cur = con.cursor()

c = cur.execute("""SELECT id, first_name, middle_name, last_name FROM swimmers WHERE id not in (1, 2, 3)""")
swimmers = cur.fetchall()

count = []

for swimmer in swimmers:
    s = cur.execute(f"SELECT count(*) FROM entries WHERE swimmer = {swimmer[0]} AND seed != 'RL'")
    l = cur.fetchall()
    r = cur.execute(f"SELECT count(*) FROM relays WHERE {swimmer[0]} in (swimmer_1, swimmer_2, swimmer_3, swimmer_4)")
    j = cur.fetchall()
    name = f"{swimmer[3]}, {swimmer[1]} {swimmer[2]}".strip()
    count.append([l[0][0] + j[0][0], name])

count.sort(key=lambda x: x[0], reverse=True)

print(tabulate.tabulate(count, headers=["SWIMS", "NAME"], tablefmt='orgtbl'))
#sorted = sorted(count.items(), key=lambda x: x[1], reverse=True)
#count = dict(sorted)
#for swimmer in count:
#    print(f"{swimmer} - {count[swimmer]}")

print(f"Total Swimmers - {len(swimmers)}")
