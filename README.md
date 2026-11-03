# Egesha

Egesha (Swahili for "park") is a web-based parking system I built with Python, Flask and SQLite.

## What it does

* Shows all parking slots on screen, green for free and red for occupied
* Records a vehicle when it arrives and gives it the nearest free slot
* On exit, works out how long the vehicle stayed and the fee, takes payment, then opens the barrier
* Admin page with session history and the day's revenue

## Parking fees

* Up to 30 minutes: free
* Up to 2 hours: Kshs 50
* Up to 4 hours: Kshs 100
* Up to 6 hours: Kshs 300
* Over 6 hours: Kshs 500

## How to run

&#x20;   pip install -r requirements.txt
    python app.py


Then open http://127.0.0.1:5000 in a browser.

The modules, algorithms, data structures and database design are in TASK\_ONE.md.

