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

## Beschattung (zweites Add-on)

Raffstores, Rollläden und Galeriefenster in derselben Optik wie die Wildkammer, fürs iPhone gebaut:
Übersicht mit Zählern und „Alle auf / Alle zu / Lamellen“, darunter je Raum ein Reiter mit Reglern für Höhe und Lamellen.

Installieren: im Add-on-Store (gleiches Repository) **Beschattung** installieren, starten, „In Seitenleiste anzeigen“ einschalten.

Räume und Rollos stehen in `beschattung/app/raeume.py`. Eigene Aufteilung ohne Update: `/config/beschattung.yaml`
anlegen (Aufbau siehe `BEISPIEL` in derselben Datei) und das Add-on neu starten.
