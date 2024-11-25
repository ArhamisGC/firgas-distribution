import sqlite3

# Crear base de datos e inicializar datos
def setup_database():
    conn = sqlite3.connect("vrp_data.db")
    cursor = conn.cursor()

    # Crear tabla de localizaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        demand INTEGER NOT NULL
    )
    """)

    # Crear tabla de camiones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trucks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        capacity INTEGER NOT NULL
    )
    """)

    # Limpiar tablas para evitar duplicados o datos residuales
    cursor.execute("DELETE FROM locations")
    cursor.execute("DELETE FROM trucks")

    # Insertar datos iniciales en `locations`
    cursor.executemany("""
    INSERT INTO locations (latitude, longitude, demand)
    VALUES (?, ?, ?)
    """, [
        (28.120056, -15.430251, 0),  # Punto inicial
        (28.073687556995907, -15.451800956382401, 10),
        (27.90184647216374, -15.446392923173903, 15),
        (27.765357123904156, -15.673442527691762, 20),
        (27.808588135553386, -15.483237769536828, 25),
        (27.798971369372776, -15.715452437780161, 5),
        (28.11807130798369, -15.524992806538343, 10),
        (28.132453377326556, -15.66115490051511, 15)
    ])

    # Insertar datos iniciales en `trucks`
    cursor.executemany("""
    INSERT INTO trucks (capacity)
    VALUES (?)
    """, [
        (50,),  # Capacidad del camión 1
        (40,),  # Capacidad del camión 2
        (40,)   # Capacidad del camión 3
    ])

    conn.commit()
    conn.close()
    print("Base de datos inicializada.")

if __name__ == "__main__":
    setup_database()
