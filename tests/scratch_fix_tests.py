import re
with open('tests/test_persistence.py', 'r') as f:
    content = f.read()
content = re.sub(r'recruiter_id=str\(uuid\.uuid4\(\)\)', 'recruiter_id="00000000-0000-0000-0000-000000000000"', content)
with open('tests/test_persistence.py', 'w') as f:
    f.write(content)
