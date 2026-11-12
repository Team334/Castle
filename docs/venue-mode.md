# Venue mode: scouting with no internet

Some venues have no usable signal, which means no Wi-Fi and no mobile data in the stands. Venue mode keeps Castle working there:

- **Scouts' phones** save entries with no signal and upload them later on their own.
- **The scouting lead's laptop** runs its own copy of Castle. Scouts hand their entries to it by holding up an animated QR code, and the lead uses the normal leaderboard, compare, auto paths and match list, all with no internet.

Only one laptop needs this setup. Scouts' phones need nothing installed.

## One-time laptop setup (Windows)

1. Install **Python 3.12 or newer** from python.org. Tick "Add Python to PATH".
2. Install **MongoDB Community Server** from mongodb.com/try/download/community. Keep "Install MongoDB as a Service" ticked so the database starts with the laptop.
3. Get Castle and its packages. In a terminal:
   ```
   git clone https://github.com/Team334/Castle.git
   cd Castle
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
4. Create a file called `.env` in the `Castle` folder:
   ```
   MONGO_URI=mongodb://localhost:27017/castle
   SECRET_KEY=<paste the output of: python -c "import secrets; print(secrets.token_hex(32))">
   VENUE_MODE=1
   ```
   Leave out the TBA and Statbotics keys. Venue mode works without them.
5. Create the lead's login on this laptop. No password ever leaves castlescouting.com, so this is a separate login just for the laptop:
   ```
   .venv\Scripts\flask --app wsgi venue-user --username lead --password <choose one> --team 334
   ```

## Running it

```
.venv\Scripts\python -m app
```

Then open **http://localhost:5000** and log in with the laptop login. A yellow bar at the top says "Venue mode". That's how you know you're on the laptop's copy and not castlescouting.com.

The camera on the **Scan QR** page only works at `http://localhost:5000`, and only after you allow camera access when the browser asks.

## The night before (you need internet here, e.g. hotel Wi-Fi)

1. **Clear the last event off the laptop:**
   ```
   .venv\Scripts\flask --app wsgi venue-reset
   ```
   It refuses if the laptop still holds entries scouted on it that were never downloaded. Do "After the event" first, or add `--force` if you're sure you don't need them.
2. **Download the team's data from castlescouting.com:** log in, go to **Scout → Download all (JSON)**, and save the file.
3. **Load it on the laptop:** on `http://localhost:5000`, go to **Scout → Import file** and pick that file. You'll see "Imported: N saved, …".
4. **Get every scout's phone ready while it has internet.** Each scout opens **Scout → Add match** once and picks the event. "Saved on this phone for offline use" means the form and the match schedule are on the phone.

## At the venue

- **Scouts** scout as usual. With no signal, Save keeps the entry on the phone and moves on to the next match. A bar shows "N entries waiting to upload".
  - **Match not in the list?** Tap "Match not listed? Type it in". Playoff matches and schedule changes often need this.
- **Handing entries to the lead:** the scout taps **Show QR** and holds the phone up to the laptop's camera on **Scout → Scan QR**. When the page says "Done", the scout taps **Lead has these**. A dozen or so entries take a few seconds.
- **The lead** uses the leaderboard, compare, auto paths and match list as normal. Entries marked **Fuel pending** were scouted at the venue: the AI fuel count runs once they reach castlescouting.com, so they're left out of the fuel averages until then.
- **Missing data:** team names and EPA come from TBA and Statbotics, so they're missing at the venue. The scouting numbers are all there.

## After the event (with internet)

1. On the laptop: **Scout → Download new entries**. It saves only the entries scouted on the laptop.
2. On castlescouting.com: **Scout → Import file**, and pick that file. Entries already uploaded by phones are skipped automatically.
3. Phones upload their own waiting entries as soon as they have a signal. Nothing to do.
4. Next event: start again from "The night before".

## Troubleshooting

- **Camera unavailable on Scan QR:** allow camera access in the browser's address bar, make sure you're on `http://localhost:5000`, or plug in a webcam.
- **A phone shows the "You're offline" page instead of the scout form:** it wasn't set up while online. Get it a signal once and open **Add match**.
- **"Log in to upload" on a phone:** its login expired. Log in again when there's a signal and the waiting entries upload.
- **"Not accepted: scout is not on your team":** that scout's account isn't on your team on castlescouting.com.
