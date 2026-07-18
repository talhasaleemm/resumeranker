Hi, I'm Talha, and I'd like to walk you through ResumeRanker, an AI-powered resume parsing and candidate matching platform I built to solve the core bottlenecks in technical recruitment.

When hiring for specialized roles, manually extracting skills from various document formats and objectively ranking those candidates against a job description is incredibly time-consuming. I engineered ResumeRanker to automate this entire pipeline with high precision.

At its core, the platform is driven by a FastAPI backend connected to a PostgreSQL database. To handle the initial ingestion, I built a custom Natural Language Processing pipeline using spaCy. When a candidate uploads a PDF or DOCX file, the system runs a Named Entity Recognition model to cleanly extract their skills, education, and professional experience, regardless of how the original document was formatted. 

Once the structured data is safely stored in PostgreSQL, the matching engine takes over. Instead of relying on simple keyword matching, I designed an algorithm that combines TF-IDF and BM25 scoring. This ensures that the system understands the relative importance and frequency of specific skills. It automatically normalizes the extracted data and applies weighted scoring to rank the candidates directly against the technical requirements of the job description. The engine also auto-tags profiles across domains like backend, frontend, full-stack, AI, and bioinformatics to make candidate filtering immediate.

From an infrastructure perspective, I wanted this to be a strictly production-ready application. The entire architecture is containerized using a multi-stage Docker build. I optimized the Dockerfile by baking the spaCy language models directly into the builder stage and minimizing the runtime dependencies to just what is needed, like libpq and Poppler for document processing. The system is deployed to the cloud via Render, utilizing a private network for the database and a secure web service for the API.

ResumeRanker represents a complete, end-to-end solution combining modern NLP, efficient retrieval algorithms, and robust DevOps practices. Thank you for taking the time to review the architecture.
