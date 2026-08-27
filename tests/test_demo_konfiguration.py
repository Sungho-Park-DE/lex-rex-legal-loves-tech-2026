"""Die Entscheidung vom 24. Aug (Sungho): **die Vorführung läuft nicht live.**

`llm.nur_cache = true` ist die eine Quelle dafür. Damit geht kein Aufruf ins
Netz, auch wenn auf der Bühnenmaschine ein Schlüssel in der Shell steht —
ein unbekanntes Dokument bekommt sofort den Satz aus `UNBEKANNTES_DOKUMENT`
statt zwanzig Sekunden Stille über Veranstaltungs-WLAN. Der Test hält die
Entscheidung fest, damit sie nicht in einem anderen Commit still zurückkippt;
wer sie nach dem 27. aufhebt, ändert config.json und diesen Test zusammen.
"""

from fallpruefer.adapter import live_moeglich
from fallpruefer.konfig import konfig


def test_die_vorfuehrung_laeuft_nicht_live(monkeypatch):
    assert konfig().llm.nur_cache is True, "Register C3: Bühnenmodus cache — bewusst entschieden"
    # selbst mit Schlüssel im Env bleibt der Adapter im Cache
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-auf-der-buehne-vergessen")
    assert live_moeglich() is False
