import io

p = "/app/tests/automated_ingestion_test.py"
s = open(p).read()
s = s.replace('BASE = "http://127.0.0.1:8001"', 'BASE = "http://app:8000"')
s = s.replace('D:\\talhasaleemm.github.io\\talhasaleem_CV.pdf', '/tmp/talhasaleem_CV.pdf')
open(p, "w").write(s)
print("patched BASE:", "app:8000" in s)
print("patched PDF:", "/tmp/talhasaleem_CV.pdf" in s)
