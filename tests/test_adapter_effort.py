"""`llm.effort` — der Knopf fuer den Effort-Sweep (31 par. 4), und die eine
Regel, die ihn ungefaehrlich macht.

Der Adapter sendet bis heute keinen einzigen Sonderparameter; auf Claude
Opus 5 heisst das Voreinstellung `high` mit adaptivem Denken. Der Knopf soll
das nur dort aendern, wo das Modell den Parameter kennt: bei den
Opus-Aufgaben. `classify_doc` laeuft auf Haiku 4.5, und das beantwortet
`output_config.effort` mit 400 -- ein gesetzter Effort haette die
Klassifikation jedes Live-Laufs still gekillt.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from fallpruefer.adapter.anthropic_adapter import AnthropicAdapter, LiveKlassifikation
from fallpruefer.konfig import konfig


@pytest.fixture
def adapter(monkeypatch):
    # Der Client braucht beim Bau einen Schluessel, nicht das Netz.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-nur-fuer-den-bau")
    return AnthropicAdapter(cache_lesen=False)


def test_ohne_effort_bleibt_der_aufruf_wie_er_war(adapter):
    """Voreinstellung: kein output_config -- weder fuer Opus noch fuer Haiku."""
    assert konfig().llm.effort is None
    for aufgabe in ("classify_doc", "extract_fields", "propose_fallgruppe"):
        assert adapter._ausgabe_konfig(aufgabe) == {}


def test_effort_geht_nur_an_die_opus_aufgaben(adapter, monkeypatch):
    monkeypatch.setattr(konfig().llm, "effort", "low")
    assert adapter._ausgabe_konfig("extract_fields") == {"output_config": {"effort": "low"}}
    assert adapter._ausgabe_konfig("propose_fallgruppe") == {"output_config": {"effort": "low"}}
    assert adapter._ausgabe_konfig("classify_doc") == {}, "Haiku 4.5 kennt effort nicht (400)"


def test_die_klassifikation_bekommt_auch_live_keinen_effort(adapter, monkeypatch):
    """Am Aufruf selbst gemessen, nicht am Helfer: der gestubbte Client sieht,
    was wirklich gesendet wird."""
    monkeypatch.setattr(konfig().llm, "effort", "low")
    gesehen: dict = {}

    def parse(**kwargs):
        gesehen.update(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            stop_details=None,
            parsed_output=LiveKlassifikation.model_construct(),
            usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )

    monkeypatch.setattr(adapter._client, "messages", SimpleNamespace(parse=parse))
    adapter._live("classify_doc", konfig().llm.modell_klassifikation,
                  {"seiten": [{"nr": 1, "text": "Mitgliedsvertrag"}]})
    assert "output_config" not in gesehen
    assert gesehen["model"] == konfig().llm.modell_klassifikation
