import sqlite3
import re

APP_DB = r"C:\Users\czion\Documents\Codex\2026-11-11\c-program-files-x86-steam-steamapps\outputs\app\번역.sqlite"
BAK_DB = r"C:\Users\czion\Documents\Codex\2026-11-11\c-program-files-x86-steam-steamapps\outputs\app\번역.sqlite.bak"

conn_app = sqlite3.connect(APP_DB)
conn_bak = sqlite3.connect(BAK_DB)

rows_app = conn_app.execute("SELECT id, context, field, en, ru, ko, status, note FROM entries ORDER BY id").fetchall()
rows_bak = {r[0]: r for r in conn_bak.execute("SELECT id, context, field, en, ru, ko, status, note FROM entries ORDER BY id")}

status_diffs = 0
note_diffs = 0
ko_changed = 0
tag_errors = []
var_errors = []
hyphen_gi = []
meta_leaks = []

for id_, ctx, fld, en, ru, ko, status, note in rows_app:
    bak = rows_bak[id_]
    if status != bak[6]:
        status_diffs += 1
    if note != bak[7]:
        note_diffs += 1
    if ko != bak[5]:
        ko_changed += 1
        # Verify tags and variables on every modified row (and all rows)
        for v in ["<username>", "<userlastname>", "{0}"]:
            if (v in en) != (v in ko):
                var_errors.append((id_, v, en, ko))
        # Check balanced <male>/</male>, <female>/</female>, <color>/</color>
        for tag in ["male", "female"]:
            if ko.count(f"<{tag}>") != ko.count(f"</{tag}>"):
                tag_errors.append((id_, f"unbalanced {tag}", ko))
        if ko.count("<color") != ko.count("</color>") and en.count("<color") == en.count("</color>"):
            tag_errors.append((id_, "unbalanced color", ko))
    if " -기" in ko or "-기" in ko:
        hyphen_gi.append((id_, ko))
    if re.search(r"가 아닌 [‘']|직역하면|번역하자면", ko):
        meta_leaks.append((id_, ko))

print(f"Total rows: {len(rows_app)}")
print(f"Total ko updated vs .bak: {ko_changed}")
print(f"status_diffs: {status_diffs}")
print(f"note_diffs: {note_diffs}")
print(f"var_errors on updated rows: {len(var_errors)}")
for e in var_errors:
    print("  VAR ERROR:", e)
print(f"tag_errors on updated rows: {len(tag_errors)}")
for e in tag_errors:
    print("  TAG ERROR:", e)
print(f"hyphen_gi remaining: {len(hyphen_gi)}")
for e in hyphen_gi:
    print("  HYPHEN GI:", e)
print(f"meta_leaks remaining: {len(meta_leaks)}")
for e in meta_leaks:
    print("  META LEAK:", e)
