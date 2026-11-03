# Task One: Egesha Parking System

## Modules
1. Slot management: keeps track of free and occupied slots and feeds the slot display
2. Vehicle entry: checks the plate, records arrival time and allocates a slot
3. Fee calculation: works out time parked and the amount due
4. Payment: records how the driver paid (cash, M-Pesa or card)
5. Exit and barrier control: opens the barrier only after payment and frees the slot
6. Admin and reporting: session history and revenue

## a) Algorithms

Entry
1. Read the plate, remove spaces, change to uppercase and validate it.
2. If the plate is already inside, reject it.
3. If there is no free slot, show that the parking is full.
4. Take the lowest-numbered free slot.
5. Save the session with plate, slot and entry time, and mark the slot occupied.
6. Show the driver their slot number.

Fee calculation
1. minutes = (exit time - entry time) / 60
2. If minutes <= 30, fee = 0
3. Else if minutes <= 120, fee = 50
4. Else if minutes <= 240, fee = 100
5. Else if minutes <= 360, fee = 300
6. Else fee = 500

Exit and payment
1. Read the plate and find its active session. If none, show an error.
2. Set exit time to now and calculate the fee.
3. Show the bill and take payment.
4. Save the exit time, fee and payment, and mark the session completed.
5. Mark the slot free and make it available again.
6. Open the barrier.

Slot display
1. Get every slot from the database.
2. Draw green for free and red for occupied.
3. Count the free slots and show the total.
4. Repeat every 5 seconds.

## b) Data structures and why I used them
- Min-heap for the free slots. It always gives the lowest free slot number quickly, in O(log n), and putting a slot back is also O(log n).
- Hash map (dictionary) from plate to session id. Finding a vehicle on exit and checking for duplicate entry are both O(1).
- List for the slot grid, since the slots are shown in a fixed order.
- Records (rows) for sessions, so the plate, slot and times stay together.

The database is the permanent record. The heap and dictionary are rebuilt from it each time the system starts.

## c) Dynamic database design

slots (slot_id PK, slot_number, status)
sessions (session_id PK, plate, slot_id FK, entry_time, exit_time, fee, status)
payments (payment_id PK, session_id FK, amount, method, paid_at)

One slot can have many sessions over time, and each session has one payment. The database is dynamic because rows are added and updated while the system runs: a session is created on entry and updated on exit, and slot status changes each time. New slots can be added by inserting rows without touching the code. An index on sessions (plate, status) makes exit lookups faster.
