import sqlite3

DB_NAME = "market.db"

def reset_db():
    """Delete all data from the prices table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prices")
    conn.commit()
    conn.close()
    print("Database has been reset. All rows deleted.")

if __name__ == "__main__":
    # Reset the database if you want
    reset_db()
