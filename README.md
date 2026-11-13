# Wildkammer

Home-Assistant-Add-on für Fleisch-, Wurst- und Honigverwaltung mit Niimbot-B1-Etiketten,
Kunden, Bestellungen und Packliste.

## Installieren

1. Home Assistant → Einstellungen → Add-ons → Add-on-Store → ⋮ → **Repositories**
2. `https://github.com/Hackhuebi/Wildkammer-` hinzufügen
3. **Wildkammer** installieren und starten

Beim Start spielt das Add-on die Dateien aus `wildkammer/pakete` nach `/config/packages` ein,
sichert die alten Fassungen in `/config/wildkammer-sicherung`, lässt Home Assistant die Konfiguration
prüfen und lädt neu. Bei einem Fehler bleibt die alte Fassung aktiv.

Einrichtung, Sprachbefehle und Claude-Anbindung: siehe `ANLEITUNG-VERKAUF.md` und `ANLEITUNG-SPRACHE.md`.
