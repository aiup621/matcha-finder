import io, sys, re, os
p = "light_extract.py"
if not os.path.exists(p):
    print("light_extract.py not found"); sys.exit(1)
s = io.open(p, "r", encoding="utf-8").read()
orig = s

# 代表パターン: dec = _decode_cfemail(enc); if dec: emails.add(dec)
s = re.sub(r'(\b\w+\s*=\s*_decode_cfemail\([^)]*\))\s*;\s*if\s+(\w+)\s*:\s*emails\.add\(\s*\2\s*\)',
           r'\1\nif \2:\n    emails.add(\2)', s)

# 予備: 文字列置換（念のため）
s = s.replace('dec = _decode_cfemail(enc); if dec: emails.add(dec)',
              'dec = _decode_cfemail(enc)\nif dec:\n    emails.add(dec)')
s = s.replace('m = _decode_cfemail(enc); if m: emails.add(m)',
              'm = _decode_cfemail(enc)\nif m:\n    emails.add(m)')

# 万一 emails.add(m) のままなら dec に統一
s = re.sub(r'emails\.add\(\s*m\s*\)', 'emails.add(dec)', s)

if s != orig:
    io.open(p, "w", encoding="utf-8").write(s)
    print("patched: yes")
else:
    print("patched: no-change")
