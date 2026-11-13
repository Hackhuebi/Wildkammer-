# Sprachtest mit Home Assistant Assist

Damit sagst du nur noch „Braten 800 Gramm“. Am iPhone testest du das, bevor du ein Gerät kaufst. **Bestehende Alexa-Routinen funktionieren weiter**, aber du brauchst sie dafür nicht.

## 1. Update einspielen

1. Starte **Samba share** und kopiere den Ordner `wildkammer` aus dieser ZIP-Datei nach `\\192.168.178.60\addons`. Vorhandene Dateien überschreibst du.
2. Öffne **Einstellungen → Add-ons → Add-on Store**, wähle **Nach Updates suchen** und öffne „Wildkammer“. Aktualisiere oder baue es neu, bis Version 1.2.0 läuft.
3. Ersetze `config/packages/wildetikett.yaml` durch die neue Datei.
4. Prüfe unter **Entwicklerwerkzeuge → YAML** die Konfiguration und starte Home Assistant vollständig neu. Die bekannte Modbus-Meldung darfst du ignorieren.

## 2. Assist einstellen

Öffne **Einstellungen → Sprachassistenten** und dann deinen Assistenten oder einen neuen:

- **Sprache:** Deutsch
- **Spracherkennung:** Home Assistant Cloud
- **Sprachausgabe:** Home Assistant Cloud

## 3. Erst tippen

Öffne in der Home-Assistant-App oder im Browser das Assist-Symbol und **tippe** die Sätze. So siehst du, ob die Befehle stimmen, unabhängig von der Spracherkennung:

1. `Braten`: Antwort „Erst die Wildart sagen.“, kein Etikett
2. `Reh`: Antwort „Reh, Stück …“
3. `Braten 800 Gramm`: Etikett mit `800 g`
4. `Hack`: Etikett ohne Gewicht
5. `Keule 1,5 Kilo`: Etikett mit `1,5 kg`
6. `drei mal Gulasch`: drei Etiketten
7. `Storno`: letzte Tüte fällt aus dem Bestand
8. `Rücken im Ofen`: „Das Gewicht habe ich nicht verstanden.“, kein Etikett
9. `Wie viel Hack habe ich noch`: nennt den Bestand

Prüfe danach unter `http://192.168.178.60:8099` den Bestand, und storniere oder lagere die Testtüten aus.

**Fehlerfall:** Schalte den B1 aus und tippe `Braten`. Die Antwort muss vom Drucker handeln, und es darf keine Tüte dazukommen.

## 4. Dann sprechen

Geh in den Jagdraum und sprich die Sätze über das Mikrofon in Assist. Lass auch den Vakuumierer laufen.

Zähl mit: Wie oft stimmen Teilstück und Gewicht bei zehn Versuchen? Notiere falsch verstandene Sätze, denn Assist zeigt dir den erkannten Text an.

## Was du sagen kannst

| Satz | Wirkung |
|---|---|
| Reh / Wildart Schwarzwild / Wildschwein | Setzt die Wildart |
| Braten / Etikett Braten | Etikett ohne Gewicht |
| Braten 800 Gramm / Braten achthundert Gramm | Etikett mit Gewicht |
| Keule 1,5 Kilo / Keule anderthalb Kilo / Keule 1 Kilo 200 | Etikett mit Gewicht |
| Drei mal Gulasch / Dreimal Gulasch 500 Gramm | Mehrere Etiketten, je mit diesem Gewicht |
| Nochmal | Druckt das letzte Etikett erneut |
| Storno | Nimmt die zuletzt gedruckte Tüte heraus |
| Neues Stück | Nächstes Tier derselben Wildart |
| Wie viel Hack habe ich noch / Bestand Hack | Sagt den Bestand an |

## Wörter ändern

Satzmuster stehen in `wildetikett.yaml` unter `automation:`. Für ein neues Teilstück kopierst du dort die Blöcke eines vorhandenen Teilstücks, sowohl in `wild_sprache_etikett` als auch in `wild_sprache_bestand`. Danach lädst du die Automatisierungen neu.
