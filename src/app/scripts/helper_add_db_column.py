import sqlite3
import os


column_name = "team_description"
column_type = "TEXT"
db_dir = "../../../db"


def add_column_to_table(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute(f"ALTER TABLE teams ADD COLUMN {column_name} {column_type}")
    except sqlite3.OperationalError as e:
        print(f"Error adding column to {db_file}: {e}")
    else:
        print(f"Column added to {db_file}")
    conn.commit()
    conn.close()


def main():
    for root, dirs, files in os.walk(db_dir):
        for file in files:
            if file.endswith(".db"):
                db_file = os.path.join(root, file)
                add_column_to_table(db_file)


if __name__ == "__main__":
    main()
