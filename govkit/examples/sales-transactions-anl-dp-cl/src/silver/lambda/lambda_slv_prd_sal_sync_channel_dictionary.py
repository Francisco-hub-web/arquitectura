"""Sincroniza el diccionario de canales (src/silver/dictionary) hacia el seed dbt."""
import json
import os

DICTIONARY = os.path.join(os.path.dirname(__file__), "..", "dictionary", "sales_channel.json")


def handler(event, context):
    with open(DICTIONARY, encoding="utf-8") as fh:
        channels = json.load(fh)
    return {"status": "ok", "channels": len(channels)}
