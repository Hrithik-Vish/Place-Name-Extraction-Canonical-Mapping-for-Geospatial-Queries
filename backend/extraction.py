import spacy
from db import get_supabase

try:
    nlp = spacy.load("en_core_web_sm")
except:
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Small fallback list for common places spaCy might miss
INDIAN_CITIES = [
    "Goa", "Panaji", "Pune", "Nashik", "Thane", "Kalyan"
]


def extract_places(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    
    places = []
    
    # Step 1: spaCy NER
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            if ent.text not in places:
                places.append(ent.text)
    
    # Step 2: Fallback (hardcoded list)
    for city in INDIAN_CITIES:
        if city in text and city not in places:
            places.append(city)
    
    return places