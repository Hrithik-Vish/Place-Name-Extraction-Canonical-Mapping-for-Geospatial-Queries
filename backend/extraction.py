import spacy

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except:
    print("⚠️ Downloading spaCy model...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_places(text: str) -> list[str]:
    """Extract place names using spaCy NER."""
    if not text or not text.strip():
        return []
    
    doc = nlp(text)
    places = []
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            places.append(ent.text)
    
    return places


# Test
if __name__ == "__main__":
    print(extract_places("I am in Thane, near Kalyan"))  # ['Thane', 'Kalyan']