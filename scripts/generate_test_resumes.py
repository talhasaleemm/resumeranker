# -*- coding: utf-8 -*-
"""
scripts/generate_test_resumes.py - Generate realistic test resume text files.

Creates test_data/ at the project root and writes three candidate resumes
with distinct tech stacks for frontend, backend, and DevOps roles.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_DIR = os.path.join(PROJECT_ROOT, "test_data")

RESUMES = {
    "candidate_alice.txt": """
ALICE MARTINEZ
alice.martinez@email.com | (555) 123-4567 | linkedin.com/in/alicemartinez

SUMMARY
Frontend Engineer with 5+ years of experience building responsive web applications
with React, TypeScript, and modern CSS architectures. Passionate about accessibility,
performance, and design systems.

EXPERIENCE
Senior Frontend Engineer - TechCorp Inc. (2021 - Present)
- Architected a React Design System serving 12 product teams, reducing UI bugs by 35%.
- Migrated legacy jQuery codebase to Next.js + TypeScript, improving Lighthouse scores
  from 42 to 91.
- Implemented unit and integration tests with Jest and React Testing Library, raising
  coverage from 40% to 87%.
- Led code reviews and mentored 3 junior engineers.

Frontend Developer - DigitalAgency Co. (2019 - 2021)
- Built client-facing dashboards using React, Redux, and Tailwind CSS.
- Optimized bundle size by 30% via code splitting and dynamic imports.
- Collaborated with UX designers to implement pixel-perfect Figma prototypes.

Junior Web Developer - StartupXYZ (2017 - 2019)
- Developed marketing websites and landing pages with HTML, SCSS, and vanilla JS.
- Integrated Stripe payments and Mailchimp automation for e-commerce clients.

SKILLS
JavaScript, TypeScript, React, Next.js, Vue.js, HTML5, CSS3, Tailwind CSS,
Sass/SCSS, Redux, Zustand, Jest, React Testing Library, Cypress, Webpack,
Vite, Git, Figma, REST APIs, GraphQL, WebSockets, Chrome DevTools,
Accessibility (WCAG), Performance Optimization, Responsive Design

EDUCATION
B.S. Computer Science - University of Technology (2017)
- GPA: 3.8 / 4.0
- Senior project: Real-time collaborative editor using WebSockets and CRDTs

CERTIFICATIONS
- Meta Frontend Developer Professional Certificate (2022)
- AWS Cloud Practitioner (2023)
""".strip(),

    "candidate_bob.txt": """
BOB CHEN
bob.chen@email.com | (555) 987-6543 | linkedin.com/in/bobchen

SUMMARY
Backend Engineer specializing in Python, FastAPI, and distributed systems.
6+ years of experience designing scalable APIs, optimizing database performance,
and building resilient microservices.

EXPERIENCE
Senior Backend Engineer - DataStream Systems (2020 - Present)
- Designed and shipped 3 FastAPI microservices handling 50K+ requests/minute.
- Reduced PostgreSQL query latency by 60% through indexing, connection pooling,
  and query optimization.
- Implemented event-driven architecture with Kafka for real-time analytics pipeline.
- Led migration from Celery 4 to Celery 5, reducing task queue latency by 25%.

Software Engineer - CloudNetworks (2018 - 2020)
- Built RESTful APIs with Django and Django REST Framework.
- Integrated Stripe webhooks and PostgreSQL triggers for financial reporting.
- Containerized services with Docker and deployed via AWS ECS.

Backend Developer - FinTech Startup (2016 - 2018)
- Developed payment processing endpoints using Python and Redis.
- Wrote comprehensive pytest suites achieving 92% code coverage.
- Participated in on-call rotations and incident response for production outages.

SKILLS
Python, FastAPI, Django, Flask, SQLAlchemy, Alembic, PostgreSQL, Redis,
Celery, Kafka, Docker, Kubernetes, AWS (EC2, ECS, RDS), gRPC, GraphQL,
REST APIs, OAuth2, JWT, pytest, CI/CD, GitHub Actions, Terraform,
Datadog, Prometheus, Grafana, Linux, Bash, Git, Microservices

EDUCATION
M.S. Computer Science - State University (2016)
- Focus: Distributed Systems and Database Optimization
- Teaching assistant for Graduate Databases course

CERTIFICATIONS
- AWS Solutions Architect - Associate (2022)
- Certified Kubernetes Administrator (CKA) (2023)
""".strip(),

    "candidate_charlie.txt": """
CHARLIE "CHAD" PATEL
charlie.patel@email.com | (555) 456-7890 | linkedin.com/in/charliepatel

SUMMARY
DevOps Engineer with 7+ years of experience bridging development and operations.
Expertise in containerization, infrastructure-as-code, CI/CD pipelines, and
cloud-native architectures on AWS and Azure.

EXPERIENCE
Staff DevOps Engineer - EnterpriseCloud Ltd. (2019 - Present)
- Architected Kubernetes clusters on EKS serving 200+ microservices.
- Reduced deployment time from 45 minutes to 4 minutes via GitOps with ArgoCD.
- Built Terraform modules managing $2M+ in cloud infrastructure across 3 accounts.
- Implemented comprehensive monitoring stack (Prometheus, Grafana, OpsGenie)
  reducing MTTR by 70%.

DevOps Engineer - SaaS Platform Inc. (2017 - 2019)
- Migrated on-premises workloads to AWS using Docker and ECS.
- Automated provisioning with CloudFormation and Ansible.
- Set up centralized logging with ELK stack (Elasticsearch, Logstash, Kibana).

Systems Administrator - ManagedHosting Co. (2015 - 2017)
- Administered 500+ Linux servers running RHEL/CentOS.
- Automated routine maintenance with Bash and Python scripts.
- Maintained 99.99% uptime SLA for customer-facing infrastructure.

SKILLS
Docker, Kubernetes, Helm, Terraform, Ansible, AWS, Azure, GCP, Linux,
Bash, Python, Go, Jenkins, GitHub Actions, GitLab CI, ArgoCD, Prometheus,
Grafana, ELK Stack, Splunk, Nginx, HAProxy, Istio, Vault, PostgreSQL,
Redis, RabbitMQ, Kafka, CloudFormation, CDK, Pulumi, REST APIs,
On-call rotation, Incident Management, SLO/SLI/SLA, Cost Optimization

EDUCATION
B.S. Information Technology - Polytechnic Institute (2015)
- Concentration: Network Operations and Security

CERTIFICATIONS
- AWS DevOps Engineer - Professional (2022)
- Certified Kubernetes Administrator (CKA) (2021)
- HashiCorp Certified: Terraform Associate (2023)
""".strip(),
}


def main():
    if not os.path.exists(TEST_DATA_DIR):
        os.makedirs(TEST_DATA_DIR)

    for filename, content in RESUMES.items():
        filepath = os.path.join(TEST_DATA_DIR, filename)
        with open(filepath, "w") as f:
            f.write(content)
        print("Created: test_data/" + filename)

    print("\nGenerated " + str(len(RESUMES)) + " test resumes in test_data/")


if __name__ == "__main__":
    main()
