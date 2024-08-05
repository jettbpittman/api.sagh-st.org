import psycopg2
import json

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

c = cur.execute("""SELECT * FROM swimmers""")
swimmers = cur.fetchall()

count = dict()

for swimmer in swimmers:
    s = cur.execute(f"SELECT count(*) FROM entries WHERE swimmer = {swimmer[0]}")
    l = cur.fetchall()
    name = f"{swimmer[3]}, {swimmer[1]} {swimmer[2]}".strip()
    count.update({name: l[0][0]})

r = cur.execute("""SELECT * FROM relays""")
relays = cur.fetchall()

c = cur.execute("""SELECT""")

for relay in relays:
    counter = 1
    while counter < 5:
        cur.execute(f"SELECT first_name, middle_name, last_name FROM swimmers WHERE id = {relay[counter]}")
        l = cur.fetchall()
        name = f"{l[0][2]}, {l[0][0]} {l[0][1]}".strip()
        count[name] += 1
        counter += 1

rcount = dict(sorted(count.items(), key=lambda item: item[1], reverse=True))

for line in rcount:
    print(f"{line} - {rcount[line]}")

#sorted = sorted(count.items(), key=lambda x: x[1], reverse=True)
#count = dict(sorted)
#for swimmer in count:
#    print(f"{swimmer} - {count[swimmer]}")

print(f"Total Swimmers - {len(swimmers)}")
