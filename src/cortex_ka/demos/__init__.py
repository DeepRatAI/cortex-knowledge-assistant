"""Demo seeders for different domain scenarios.

Cortex is domain-agnostic. These seeders demonstrate versatility
by populating the database with realistic data for various industries.

Available demos:
- seed_university: FCE-IUC (private university / economics faculty)
- ingest_university_corpus: Ingest FCE-IUC documentation into Qdrant
- (future) seed_banking: Banking/financial institution
- (future) seed_clinic: Private healthcare clinic

Usage:
    python -m cortex_ka.demos.seed_university --clean
    python -m cortex_ka.demos.ingest_university_corpus --clean
"""

from .ingest_university_corpus import ingest_university_corpus
from .seed_university import UniversitySeedResult, seed_university_demo

__all__ = ["seed_university_demo", "UniversitySeedResult", "ingest_university_corpus"]
