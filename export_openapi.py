# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
import json
from main import app

def generate_openapi_spec():
    openapi_data = app.openapi()
    with open("openapi.json", "w") as f:
        json.dump(openapi_data, f, indent=2)
    print("Exported openapi.json successfully!")

if __name__ == "__main__":
    generate_openapi_spec()