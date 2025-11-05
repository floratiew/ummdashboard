import sqlite3

conn = sqlite3.connect('data/umm_messages.db')
cursor = conn.cursor()

# Get total messages (outage types: 1=Production, 2=Consumption, 3=Transmission)
cursor.execute("SELECT COUNT(*) FROM messages WHERE message_type IN (1, 2, 3)")
total_messages = cursor.fetchone()[0]

# Count total area occurrences (split by comma)
cursor.execute("SELECT area_names FROM messages WHERE message_type IN (1, 2, 3)")
total_area_occurrences = 0
for row in cursor.fetchall():
    if row[0]:
        # Count commas + 1 to get number of areas
        areas = [a.strip() for a in row[0].split(',') if a.strip()]
        total_area_occurrences += len(areas)

avg_areas = total_area_occurrences / total_messages if total_messages > 0 else 0

print(f"📊 Outage Count Analysis")
print(f"=" * 50)
print(f"Total market messages (types 1,2,3): {total_messages:,}")
print(f"Total area occurrences:              {total_area_occurrences:,}")
print(f"Average areas per message:           {avg_areas:.2f}")
print(f"")
print(f"💡 Explanation:")
print(f"   Each message can affect multiple price areas.")
print(f"   When counting 'outages', we count each area")
print(f"   separately, so 1 message affecting 3 areas")
print(f"   = 3 outage events.")

conn.close()
