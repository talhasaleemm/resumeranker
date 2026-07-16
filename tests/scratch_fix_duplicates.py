import uuid

with open('tests/test_persistence.py', 'r') as f:
    content = f.read()
    
# Fix recruiter_id replacement:
content = content.replace('recruiter_id=str(uuid.uuid4())', 'recruiter_id="00000000-0000-0000-0000-000000000000"')

# Make text strings dynamic by adding str(uuid.uuid4()) inside the function scope or appending a random string.
# Since we just want them unique per run, using {uuid.uuid4()} in f-strings works if we do it right.
content = content.replace('raw_text="I am a persistent developer."', 'raw_text=f"I am a persistent developer. {uuid.uuid4()}"')
content = content.replace('raw_text="I am candidate 1"', 'raw_text=f"I am candidate 1 {uuid.uuid4()}"')
content = content.replace('raw_text="I am candidate 2"', 'raw_text=f"I am candidate 2 {uuid.uuid4()}"')

with open('tests/test_persistence.py', 'w') as f:
    f.write(content)

with open('tests/test_matches_endpoint.py', 'r') as f:
    content = f.read()

content = content.replace('raw_text="I am a backend developer writing Python and React code for my web apps. I have a B.S. in Computer Science."', 'raw_text=f"I am a backend developer writing Python and React code for my web apps. I have a B.S. in Computer Science. {uuid.uuid4()}"')
content = content.replace('raw_text="I program in Java and Spring Boot."', 'raw_text=f"I program in Java and Spring Boot. {uuid.uuid4()}"')

with open('tests/test_matches_endpoint.py', 'w') as f:
    f.write(content)
