"""Test entity extraction"""
import sys
import os

# Add python_enrichment directory to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
python_enrichment_path = os.path.join(project_root, "python_enrichment")
sys.path.insert(0, python_enrichment_path)

from app import extract_subjects

test_cases = [
    "who is pavement?",
    "who is mike jones?",
    "what about wet leg",
    "tell me about radiohead",
    "yo bot who is pavement?",
]

print("Testing entity extraction:")
print("=" * 60)
for test in test_cases:
    subjects = extract_subjects(test)
    print(f"\nInput: {test}")
    print(f"Extracted: {subjects}")
