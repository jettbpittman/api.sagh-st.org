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

c = cur.execute("""SELECT * FROM swimmers WHERE active = true""")
swimmers = cur.fetchall()

count = dict()
tiscas = {}

for swimmer in swimmers:
    name = f"{swimmer[3]}, {swimmer[1]} {swimmer[2]}"
    cur.execute(f"SELECT * FROM entries WHERE swimmer = {swimmer[0]}")
    l = cur.fetchall()
    for entry in l:
        if str(entry[7]).startswith("TISCA"):
            cur.execute(f"SELECT name FROM meets WHERE id = {entry[2]}")
            m = cur.fetchone()
            try:
                tiscas[name].append({"event": entry[3], "time": entry[5], "meet": m[0]})
            except KeyError:
                tiscas[name] = [{"event": entry[3], "time": entry[5], "meet": m[0]}]

myKeys = list(tiscas.keys())
myKeys.sort()
sorted_tiscas = {i: tiscas[i] for i in myKeys}


output = ""

for i in sorted_tiscas:
    output += i + "\n===========\n"
    for e in tiscas[i]:
        output += f"{e['event']}  -  {e['time']}  -  {e['meet']}\n"
    output += "\n"
print(output)

with open("tisca_qualifiers.txt", "w") as f:
    f.write(output)
