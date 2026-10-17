# Preisfehler-Radar

Eine GitHub-Pages-Seite, die Amazon-Preisfehler aus öffentlichen Deal-Feeds (mydealz, Preisjäger, DealDoktor) sammelt und dir bei jedem neuen Fund sofort eine Push-Nachricht aufs Handy schickt.

- **Tracker:** `tracker/track.py` (nur Python-Standardbibliothek), läuft per GitHub Action etwa alle 5 Minuten
- **Webseite:** `docs/` (wird von GitHub Pages ausgeliefert, liest `docs/deals.json`)
- **Push:** [ntfy](https://ntfy.sh) (kostenlos, ohne Account) und optional Telegram

> Amazon selbst wird nicht gescrapt (technisch blockiert und gegen die Nutzungsbedingungen). Die Quelle sind Community-Meldungen – ein Preisfehler taucht also erst auf, wenn ihn jemand meldet.

## Einrichten (ca. 5 Minuten)

1. **Repo anlegen:** Neues **öffentliches** GitHub-Repo erstellen (öffentlich = Actions und Pages kostenlos) und diesen Ordner hochladen.
2. **Pages aktivieren:** *Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`*.
3. **Handy-Push (ntfy):**
   - App **ntfy** installieren (Android / iPhone).
   - Ein langes, zufälliges Thema ausdenken, z. B. `preisfehler-x7k2q9m4` und in der App abonnieren (oder auf der Seite im Abschnitt „Alarm“ eintragen und „In ntfy öffnen“ tippen).
   - *Settings → Secrets and variables → Actions → New repository secret*: Name `NTFY_TOPIC`, Wert = dein Thema.
4. **Action starten:** *Actions → „Preisfehler prüfen“ → Run workflow*. Danach läuft sie automatisch.
5. Optional **Telegram:** Bot über @BotFather anlegen und die Secrets `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` setzen.

Der erste Lauf füllt nur die Liste und sendet **keine** Pushes (damit du nicht mit alten Funden zugespammt wirst).

## Einstellungen (`tracker/config.json`)

| Schlüssel | Bedeutung |
|---|---|
| `feeds` | Quellen. `all_are_errors: true` = jeder Beitrag des Feeds gilt als Preisfehler |
| `notify_only_amazon` | `true` = Push nur für Amazon-Funde, `false` = alle Shops |
| `max_age_hours_for_push` | Ältere Beiträge lösen keinen Push aus |
| `keep_days` / `max_deals` | Wie lange/wie viele Funde die Seite behält |

## Lokal testen

```bash
python tracker/track.py            # schreibt docs/deals.json
NTFY_TOPIC=dein-thema python tracker/track.py   # mit Push
python -m http.server -d docs 8000 # Seite unter http://localhost:8000
```

## Grenzen

- GitHub-Cron ist nicht sekundengenau (meist 5–15 Min. Verzögerung). Für echte Echtzeit bräuchte es einen eigenen Server.
- Ein Preisfehler kann stornierte Bestellungen bedeuten – der Händler entscheidet.
- Die Datenquelle bestimmt die Qualität: Treffer können auch Fehlalarme sein.
