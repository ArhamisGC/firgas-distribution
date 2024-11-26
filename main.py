#TODO:implementar API de tráfico
#TODO:acutaulización cada 10 minutos
#TODO:corregir información
import sqlite3
import openrouteservice
import folium
import geocoder
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List, Tuple


ORS_API_KEY = "claveAPI"
client = openrouteservice.Client(key=ORS_API_KEY)

import requests
from typing import Tuple

def get_precise_location(api_key: str) -> Tuple[float, float]:
    """
    Obtiene la ubicación precisa utilizando la API de BigDataCloud.
    :param api_key: Tu clave de API de BigDataCloud.
    :return: Una tupla (latitud, longitud).
    """
    url = f"https://api.bigdatacloud.net/data/ip-geolocation?key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        latitude = data.get("location", {}).get("latitude")
        longitude = data.get("location", {}).get("longitude")
        if latitude is not None and longitude is not None:
            print(f"Ubicación obtenida: Latitud {latitude}, Longitud {longitude}")
            return latitude, longitude
        else:
            raise ValueError("No se pudo extraer latitud y longitud del resultado.")
    else:
        raise ValueError(f"Error en BigDataCloud API: {response.status_code} - {response.text}")


def read_database():
    conn = sqlite3.connect("vrp_data.db")
    cursor = conn.cursor()

    # Verifica si existen las tablas requeridas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]
    if "locations" not in tables or "trucks" not in tables:
        raise sqlite3.OperationalError("La base de datos no contiene las tablas requeridas.")

    cursor.execute("SELECT latitude, longitude, demand FROM locations")
    locations = [(row[0], row[1]) for row in cursor.fetchall()]
    cursor.execute("SELECT demand FROM locations")
    demands = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT capacity FROM trucks")
    truck_capacities = [row[0] for row in cursor.fetchall()]

    conn.close()
    return locations, demands, truck_capacities



def read_database():
    conn = sqlite3.connect("vrp_data.db")
    cursor = conn.cursor()

    
    cursor.execute("SELECT latitude, longitude, demand FROM locations")
    locations = [(row[0], row[1]) for row in cursor.fetchall()]
    cursor.execute("SELECT demand FROM locations")
    demands = [row[0] for row in cursor.fetchall()]

    
    cursor.execute("SELECT capacity FROM trucks")
    truck_capacities = [row[0] for row in cursor.fetchall()]

    conn.close()
    print(len(truck_capacities))
    return locations, demands, truck_capacities


def get_distance_time_matrix(locations: List[Tuple[float, float]]) -> Tuple[List[List[float]], List[List[float]]]:
    coords = [[lng, lat] for lat, lng in locations]
    response = client.distance_matrix(
        locations=coords,
        metrics=["distance", "duration"],
        units="km"
    )
    return response["distances"], response["durations"]


def solve_vrp_with_capacity(
    time_matrix: List[List[float]], 
    demands: List[int], 
    vehicle_capacities: List[int]
) -> List[List[int]]:
    manager = pywrapcp.RoutingIndexManager(len(time_matrix), len(vehicle_capacities), 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(time_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)


    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0, 
        vehicle_capacities,
        True,
        "Capacity",
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_parameters)
    if not solution:
        raise ValueError("No se encontró una solución para el VRP.")

    routes = []
    for vehicle_id in range(len(vehicle_capacities)):
        index = routing.Start(vehicle_id)
        route = []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        routes.append(route)

    
    for i, route in enumerate(routes):
        print(f"Camión {i + 1} ruta: {route}")
    return routes


def get_route_coordinates(locations: List[Tuple[float, float]], routes: List[List[int]]) -> List[List[Tuple[float, float]]]:
    all_routes_coords = []
    for route in routes:
        route_coords = []
        for i in range(len(route) - 1):
            start_coords = [locations[route[i]][1], locations[route[i]][0]]
            end_coords = [locations[route[i + 1]][1], locations[route[i + 1]][0]]

            
            try:
                directions = client.directions(
                    coordinates=[start_coords, end_coords],
                    profile="driving-car",
                    format="geojson"
                )
                geometry = directions["features"][0]["geometry"]["coordinates"]
            
                route_coords.extend([(coord[1], coord[0]) for coord in geometry])
            except Exception as e:
                print(f"Error al obtener ruta entre {start_coords} y {end_coords}: {e}")

        all_routes_coords.append(route_coords)
    return all_routes_coords


def generate_individual_maps(
    locations: List[Tuple[float, float]], 
    routes: List[List[int]], 
    all_routes_coords: List[List[Tuple[float, float]]], 
    time_matrix: List[List[float]], 
    demands: List[int],
    drivers: List[str] 
):
    colors = ["blue", "green", "red", "purple", "orange"]
    individual_maps = []

    for vehicle_id, (route, route_coords) in enumerate(zip(routes, all_routes_coords)):
        if len(route) <= 2:
            print(f"Camión {vehicle_id + 1} no tiene rutas asignadas.")
            continue

        color = colors[vehicle_id % len(colors)]
        individual_map = folium.Map(location=locations[0], zoom_start=11)

        folium.PolyLine(
            route_coords, 
            color=color, 
            weight=5, 
            opacity=0.8, 
            tooltip=f"Ruta del Camión {vehicle_id + 1}"
        ).add_to(individual_map)

        total_distance = 0.0
        total_time = 0.0

        for i, node in enumerate(route[:-1]):
            next_node = route[i + 1]
            distance = time_matrix[node][next_node] / 1000.0 
            time = time_matrix[node][next_node] / 60.0 
            total_distance += distance
            total_time += time

            if demands[node] > 0:
                icon = "info-sign" 
            else:
                icon = "ok-sign"  

            popup_html = f"""
            <b>Parada {i + 1}</b><br>
            <b>Conductor:</b> {drivers[vehicle_id]}<br>
            <b>Distancia desde la última parada:</b> {distance:.2f} km<br>
            <b>Tiempo desde la última parada:</b> {time:.2f} minutos<br>
            <b>Demanda:</b> {demands[node]} unidades<br>
            <b>Distancia total:</b> {total_distance:.2f} km<br>
            <b>Tiempo total:</b> {total_time:.2f} minutos<br>
            """

            folium.Marker(
                locations[node],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon=icon),
            ).add_to(individual_map)

        individual_map_file = f"ruta_camion_{vehicle_id + 1}.html"
        individual_map.save(individual_map_file)
        individual_maps.append((vehicle_id + 1, individual_map_file))

    return individual_maps

def visualize_routes_and_generate_main_map_with_filters(
    locations: List[Tuple[float, float]],
    gps_location: Tuple[float, float],
    routes: List[List[int]],
    all_routes_coords: List[List[Tuple[float, float]]],
    time_matrix: List[List[float]],
    demands: List[int],
    individual_maps: List[Tuple[int, str]]
):
    map_route = folium.Map(location=locations[0], zoom_start=11)
    colors = ["blue", "green", "red", "purple", "orange"]

    for vehicle_id, (route, route_coords) in enumerate(zip(routes, all_routes_coords)):
        if len(route) <= 2:
            continue

        color = colors[vehicle_id % len(colors)]
        route_layer = folium.FeatureGroup(name=f"Camión {vehicle_id + 1}", show=True)

        folium.PolyLine(
            route_coords,
            color=color,
            weight=5,
            opacity=0.8,
            tooltip=f"Ruta del Camión {vehicle_id + 1}"
        ).add_to(route_layer)

        for i, node in enumerate(route[:-1]):
            folium.Marker(
                locations[node],
                popup=(f"<b>Parada {i + 1}</b><br>Demanda: {demands[node]} unidades"),
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(route_layer)

        route_layer.add_to(map_route)

    # Agregar marcador para la localización GPS
    folium.Marker(
        gps_location,
        popup=folium.Popup("<b>Tu localización actual</b>", max_width=300),
        icon=folium.Icon(color="red", icon="user"),
    ).add_to(map_route)

    folium.LayerControl(collapsed=False).add_to(map_route)

    buttons_html = "".join([
        f"<a href='{file}' target='_blank'>Ver ruta del Camión {vehicle_id}</a><br>"
        for vehicle_id, file in individual_maps
    ])
    folium.Marker(
        locations[0],
        popup=folium.Popup(f"<b>Selecciona una ruta:</b><br>{buttons_html}", max_width=300),
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(map_route)

    return map_route


if __name__ == "__main__":
    try:
        gps_location = get_precise_location("claveAPI")
        print(f"Localización GPS detectada: {gps_location}")
    except ValueError as e:
        print(str(e))
        gps_location = None

    try:
        locations, demands, truck_capacities = read_database()
    except sqlite3.OperationalError as e:
        print(f"Error en la base de datos: {str(e)}")
        exit(1)

    print("Obteniendo matriz de distancia y tiempo...")
    distance_matrix, time_matrix = get_distance_time_matrix(locations)

    print("Resolviendo VRP...")
    routes = solve_vrp_with_capacity(time_matrix, demands, truck_capacities)

    print("Obteniendo coordenadas para rutas por carretera...")
    route_coords = get_route_coordinates(locations, routes)

    drivers = ["Conductor A", "Conductor B", "Conductor C"]

    print("Generando mapas individuales...")
    individual_maps = generate_individual_maps(
        locations, routes, route_coords, time_matrix, demands, drivers
    )

    print("Visualizando mapa principal con filtros...")
    map_route = visualize_routes_and_generate_main_map_with_filters(
        locations, gps_location, routes, route_coords, time_matrix, demands, individual_maps
    )
    map_route.save("rutas_principal.html")
    print("Mapa guardado en 'rutas_principal.html'. Ábrelo en un navegador.")