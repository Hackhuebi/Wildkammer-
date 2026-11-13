# Wildkammer 2.0: Wurst, Kunden, Bestellungen und Claude

Was neu ist:

- **Wurstlager:** Bestand, Zugänge, Inventurkorrekturen und Preise
- **Kunden und Bestellungen:** Wurst und Fleischtüten, mit den Haken „bezahlt“ und „geliefert“
- **Kilopreise für Fleisch:** optional; ohne Preis bleibt er „offen“
- **Werkzeuge für Claude:** Du schreibst oder diktierst in der Claude-App „Jonas Muster nimmt zwei Salami“, und die Bestellung landet in der Datenbank.

Bestellt werden kann nur, was frei im Lager ist. Frei heißt: im Lager und noch nicht bestellt.

## 1. Sichern

1. Lade in der Wildkammer über **Sicherung** die Datenbank herunter.
2. Lege unter **Einstellungen → System → Sicherungen** ein vollständiges Backup an.

## 2. Add-on aktualisieren

1. Starte **Samba share** und kopiere den Ordner `wildkammer` nach `\\192.168.178.60\addons`. Bestehende Dateien überschreibst du.
2. Warte, bis das Kopieren fertig ist. Öffne dann den **Add-on Store**, wähle oben rechts **Nach Updates suchen** und lade die Seite neu.
3. Öffne „Wildkammer“ und klicke **einmal** auf **Aktualisieren**. Warte, bis Version 2.10.0 läuft.

Deine Fleischdaten bleiben erhalten. Die Datenbank bekommt nur neue Tabellen dazu.

**Falls du die ChatGPT-Version „Fleischmeister“ schon installiert hast:** Lösch `config/packages/fleischmeister_wurst.yaml`. Deren Bestellungen übernimmt diese Version nicht.

## 3. Paket installieren

1. Kopiere `packages/wildkammer_verkauf.yaml` nach `config/packages/`. `wildetikett.yaml` bleibt, wie sie ist.
2. Klicke unter **Entwicklerwerkzeuge → YAML** auf **Konfiguration prüfen** und starte Home Assistant neu.

## 4. In der App einrichten

1. Öffne **Wildkammer** in der Home-Assistant-App, dann **Wurst**. Trag bei jedem Produkt den Bestand über das Feld unter **Zugang** ein.
2. Prüf die Preise, indem du ein Produkt antippst.
3. Öffne **Kunden** und dann **Bestellungen aus der bisherigen Liste übernehmen**. Dort siehst du die 11 Bestellungen über zusammen 426 € und wie viel Wurst sie brauchen.
   - Hast du den Bestand schon eingetragen, tipp nur auf **Übernehmen**.
   - Liegt die Ware im Lager, ist aber noch nicht gebucht, setz den Haken **Fehlende Wurst als Zugang buchen**.
4. Optional: Unter **Wurst → Kilopreise für Fleisch** trägst du Kilopreise ein.

In **Bestellungen** tippst du bei jeder Bestellung auf **bezahlt** oder **geliefert**. Eine versehentliche Zahlung löschst du in der Bestellung über den Mülleimer. „Geliefert“ fragt vorher nach, weil die Ware dann das Lager verlässt.

## 5. Claude anbinden

Claude verbindet sich über deine Nabu-Casa-Adresse mit Home Assistant und sieht nur, was du für Sprachassistenten freigibst.

**In Home Assistant:**

1. Öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen** und wähle **Model Context Protocol Server**.
2. Öffne **Einstellungen → Sprachassistenten → Freigeben**.
   - Gib alle Skripte frei, die mit **Wildkammer** beginnen.
   - **Nimm alles andere heraus**, vor allem Kühlzelle, Licht und Schalter. Claude kann sonst auch diese Geräte schalten.
   - Die Freigabe gilt auch für Assist am Android-Handy, nicht aber für Alexa.
3. Empfohlen: Leg unter **Einstellungen → Personen → Benutzer** einen Benutzer „Claude“ **ohne** Administratorrechte an.

**In Claude** (claude.ai oder App, je nach Abo):

1. Öffne **Einstellungen → Connectors** und füge einen benutzerdefinierten Connector hinzu.
2. Nimm als Adresse `https://DEINE-ADRESSE.ui.nabu.casa/api/mcp/assist`. Deine Adresse steht unter **Einstellungen → Home Assistant Cloud → Remote-Steuerung**.
   - Nimm bewusst die Endung `/api/mcp/assist` und nicht nur `/api/mcp`. Die Hauptadresse würde Claude Zugriff auf alles geben.
3. Wähle bei der Anmeldung „Sign in now“ und „Use Claude's published identity“. Klicke danach auf **Connect** und melde dich mit dem Benutzer „Claude“ an.
4. Prüf, dass der Connector im Chat oder im Projekt „Wildkammer“ eingeschaltet ist.

**Test:**

- „Wie ist mein Wurstbestand?“
- „Welche Bestellungen sind noch nicht bezahlt?“
- „Karl Otto Beispiel hat bezahlt.“ Claude sollte sagen, dass nichts mehr offen ist.

## 6. Anweisung für Claude

Füg diesen Text in die Anweisungen deines Claude-Projekts „Wildkammer“ ein:

```text
Du verwaltest meine Wildkammer über die Wildkammer-Werkzeuge in Home Assistant.
- Vor jeder Bestellung den Kunden mit der Kundensuche finden. Bei einem eindeutigen Treffer dessen kunde_id
  nehmen. Bei mehreren oder keinem Treffer nachfragen. Neue Kunden nur nach meiner Bestätigung anlegen.
- Pfefferbeißer gibt es als 5er-Pack und 10er-Pack. Ist das unklar, nachfragen.
- Honig: Rapshonig und Lindenhonig im 500-g-Glas, bestellt und gebucht wie Wurst.
- Fleisch wird in Tüten bestellt, mit Wildart und Teilstück, z. B. Reh und Rücken.
- Bestellt werden kann nur, was frei im Lager ist. Ist etwas nicht da, sag mir, was frei ist.
- Mehrere Bestellungen auf einmal nacheinander eintragen und danach gesammelt bestätigen:
  Bestellnummer, Kunde, Positionen, Summe.
- Rechne nie selbst. Summen, offene Beträge und den Umsatz liefert die Wildkammer.
- "X hat bezahlt": erst die offenen Bestellungen von X holen. Bei genau einer Bestellung ohne Betrag
  buchen, bei mehreren nachfragen.
- Stornieren, Inventurkorrekturen, Preisänderungen und "Lieferung zurücknehmen" nur nach meiner
  ausdrücklichen Bestätigung.
- "X will nur 3 statt 4 Salami": Bestellung von X holen und mit "Bestellung ändern" die neue
  Gesamtmenge setzen (0 entfernt das Produkt).
- Antworte kurz und auf Deutsch.
```

## Korrekturen in der App (ab 2.2.0)

Öffne die Bestellung über **Bestellungen** und tipp auf den Kundennamen.

- **Bestellung ändern** (nur offene Bestellungen): Mengen ändern, mit 0 eine Position entfernen, Wurst oder Fleisch dazunehmen, Tüten entfernen, Datum ändern. Mehr geht nur aus freiem Lager. Alles wird zusammen gespeichert oder gar nicht.
- **Lieferung zurücknehmen**: Wenn du versehentlich „geliefert“ getippt hast. Die abgebuchte Wurst kommt zurück ins Lager, Tüten zurück ins Fach, die Bestellung ist wieder offen. Bei übernommenen Altbestellungen wurde nichts abgebucht, also wird auch nichts zurückgebucht.
- **Als früher geliefert markieren**: Für Lieferungen, die schon vor dem Eintragen deines Lagerbestands passiert sind. Der Wurstbestand bleibt gleich.
- **Endgültig löschen**: Erst stornieren, dann erscheint der Knopf. Löscht auch die Zahlungen dieser Bestellung.
- **Doppelte Kunden**: Auf der Kundenseite unter „Doppelt angelegt oder Tippfehler?“ alle Bestellungen auf den richtigen Kunden übertragen. Kunden ohne Bestellungen kannst du dort löschen.

Zahlungen und Rabatt korrigierst du wie bisher auf derselben Seite.

**Wurstlager (ab 2.8.0):** Bei jedem Produkt mit + Packungen einbuchen oder mit − herausnehmen, auch gemischt bei mehreren Produkten. Unten steht, was gebucht wird. Bei Entnahmen erscheint die Auswahl für den Grund. Nur freie, nicht bestellte Ware kann raus. Passt etwas nicht, wird gar nichts gebucht.

**Heute (ab 2.8.0):** Die Startseite zeigt Hinweise (nicht eingebuchte Tüten, Fleisch über 1 Jahr, knappe Wurst unter 5 freien Packungen), was zu liefern ist, und wer noch zahlen muss. Die Packliste findest du dort, unter Bestellungen und unter Mehr.

## Auswertung und Chargen (ab 2.16.0)

Mehr → **Auswertung**: Umsatz (nach Bestelldatum) und Einnahmen (nach Zahlungstag) für einen Zeitraum, nach Produkt, nach Monat und nach Charge.

**Chargen:** Im Lager auf ein Produkt tippen → „Neue Charge beginnen“ mit Name und Kosten. Alles, was danach eingebucht wird, gehört zur neuen Charge. Verkauft wird rechnerisch aus der ältesten Charge zuerst. Pro Charge siehst du verkauft, übrig, Umsatz nach Rabatt und den Gewinn (Umsatz minus Kosten). Der Bestand bisher steht in der Charge „… Start“; deren Kosten kannst du nachtragen.

## Zahlungserinnerung (ab 2.13.0)

Mehr → **Zahlungserinnerung**: Tage (0 = aus), Uhrzeit und Handy wählen, speichern, mit „Test-Nachricht“ prüfen. Einmal am Tag ab der Uhrzeit kommt eine Nachricht mit allen Lieferungen, die länger als eingestellt unbezahlt sind. Antippen öffnet die Wildkammer.

## Notizen (ab 2.12.0)

Für Wünsche, die gerade nicht im Lager sind („wenn du mal Schwein hast, ein ganzes“): Bestellungen → **Notizen**. Text eingeben, Kunde freiwillig. Offene Notizen stehen auf „Heute“ und beim Kunden. Mit **✓ Erledigt** abhaken. Notizen sind keine Bestellungen: Sie reservieren nichts und haben keinen Betrag.

## Honig (ab 2.9.0)

Rapshonig und Lindenhonig (Glas 500 g) stehen im Reiter **Lager** unter der Wurst. Einbuchen und Entnehmen mit + und −, bestellen und ausliefern wie Wurst. Die Preise stehen anfangs auf 0,00 € – tippe auf den Namen und trag den Preis ein. Weitere Sorten legst du unten unter „Neues Produkt“ mit Art „Honig“ an.

## Packliste (ab 2.5.0)

Oben auf **Packliste** tippen, die Bestellungen ankreuzen, die du ausliefern willst, und dann auf **Packliste erstellen** tippen. Du siehst die Gesamtmengen zum Einpacken und darunter jede Bestellung mit dem Betrag, den du noch kassieren musst. **Termin herunterladen** erzeugt einen Kalendereintrag mit der ganzen Liste. **Alle als geliefert buchen** liefert alle ausgewählten Bestellungen auf einmal aus.

## Wurstetiketten per Sprache (ab 2.4.0)

Am Handy: „Okay Nabu, drucke 5 Etiketten Salami“, „drucke ein Etikett Jagdwurst“, „drucke 3 Etiketten 10er Pfefferbeißer“. Erkannt werden Salami, Jagdwurst, Knacker, Bratwurst sowie Pfefferbeißer 5er und 10er. Ohne Größe fragt Assist nach. Jedes gedruckte Etikett bucht eine Packung ins Wurstlager, die Wildart spielt dabei keine Rolle.

Auf dem Etikett stehen Produkt, Packungsnummer (P-…), Datum und ein QR-Code. Wenn du ihn scannst, öffnet sich die Packung. Dort buchst du sie mit Grund aus, z. B. Eigenverbrauch. Packungen für Kunden mit Bestellung bitte über die Bestellung ausliefern und **nicht** zusätzlich scannen, sonst zählen sie doppelt. Ein neues Produkt kannst du erst nach einer Erweiterung per Sprache drucken, über Claude geht es sofort.

## Wurstetiketten (optional)

Das Skript **Wildkammer Wurstetiketten drucken** druckt Etiketten mit Produkt und Datum und bucht jede gedruckte Packung ins Lager. Nutz es **statt** des manuellen Zugangs, sonst zählt die Ware doppelt. Scheitert der Druck, wird nichts gebucht.

## Grenzen

- **Verhörer und Fehlzuordnungen:** Claude kann sich verhören oder einen Kunden falsch zuordnen. Die Rückmeldung nach jeder Buchung ist deine Kontrolle. Ein Fehler lässt sich stornieren, solange nichts geliefert ist.
- **Internet nötig:** Claude erreicht Home Assistant über das Internet. Die App-Oberfläche funktioniert auch ohne.
- **Fleisch ohne Kilopreis:** Hier bleibt der Preis offen. „Bezahlt“ geht dann nur mit Betrag.
- **Kein Login am Port:** Port 8099 hat keine eigene Anmeldung. Gib ihn im Router niemals frei.
