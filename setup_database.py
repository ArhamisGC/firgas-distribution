import sqlite3

def setup_database_with_priorities():
    conn = sqlite3.connect("vrp_data.db")
    cursor = conn.cursor()

    # Crear tabla de localizaciones con prioridad
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        demand INTEGER NOT NULL,
        priority INTEGER NOT NULL
    )
    """)

    # Crear tabla de camiones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trucks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        capacity INTEGER NOT NULL
    )
    """)

    # Limpiar las tablas para reiniciar los datos
    cursor.execute("DELETE FROM locations")
    cursor.execute("DELETE FROM trucks")

    # Insertar datos en `locations` con prioridad
    cursor.executemany("""
    INSERT INTO locations (latitude, longitude, demand, priority)
    VALUES (?, ?, ?, ?)
    """, [
        (28.125245480930612, -15.455505284530329, 0, 0),  # Depósito central
        (28.073687556995907, -15.451800956382401, 10, 3),  # Alta prioridad
        (27.766362658038, -15.6829266234051, 25, 3),  # Alta prioridad
        (27.90184647216374, -15.446392923173903, 35, 3),   # Media prioridad
        (28.132453377326556, -15.66115490051511, 15, 2),   # Media prioridad
        (28.11807130798369, -15.524992806538343, 10, 2),   # Media prioridad
        (27.765357123904156, -15.673442527691762, 20, 1),  # Baja prioridad
        (27.918979691324402, -15.437895460337593,35,1),
        (27.858107926577542, -15.432375024790442,5,1),
        (27.770294422260395, -15.579863941436587,5,1),
        
    ])

    # Insertar datos en `trucks`
    cursor.executemany("""
    INSERT INTO trucks (capacity)
    VALUES (?)
    """, [
        (50,),  # Capacidad camión 1
        (40,),  # Capacidad camión 2
        (40,),  # Capacidad camión 3
        (30,),
    ])

    conn.commit()
    conn.close()
    print("Base de datos con prioridades inicializada.")

if __name__ == "__main__":
    setup_database_with_priorities()
