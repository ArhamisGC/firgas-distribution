import sqlite3
import openrouteservice
import folium
import requests
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List, Tuple
import schedule
import time


ORS_API_KEY = "#####"
client = openrouteservice.Client(key=ORS_API_KEY)

DEPOT_COORDS = (28.125368486169535, -15.455408725125427)

def get_distance_time_matrix(locations: List[Tuple[float, float]]) -> Tuple[List[List[float]], List[List[float]]]:
    url = "https://api.openrouteservice.org/v2/matrix/driving-car"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "locations": [[loc[1], loc[0]] for loc in locations],
        "metrics": ["distance", "duration"],
        "units": "km"
    }
    response = requests.post(url, json=body, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data["distances"], data["durations"]
    else:
        raise ValueError(f"Error en ORS Matrix API: {response.status_code} - {response.text}")

def get_route_coordinates(locations: List[Tuple[float, float]], routes: List[List[int]]) -> List[List[Tuple[float, float]]]:
    all_routes_coords = []
    for route in routes:
        route_coords = []
        for i in range(len(route) - 1):
            start_coords = [locations[route[i]][1], locations[route[i]][0]]
            end_coords = [locations[route[i + 1]][1], locations[route[i + 1]][0]]

            url = "https://api.openrouteservice.org/v2/directions/driving-car"
            headers = {"Authorization": ORS_API_KEY}
            params = {
                "start": f"{start_coords[0]},{start_coords[1]}",
                "end": f"{end_coords[0]},{end_coords[1]}",
                "format": "geojson"
            }
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                geometry = data["features"][0]["geometry"]["coordinates"]
                route_coords.extend([(coord[1], coord[0]) for coord in geometry])
            else:
                print(f"Error en ORS Directions API: {response.status_code} - {response.text}")

        all_routes_coords.append(route_coords)
    return all_routes_coords

def read_database_with_depot() -> Tuple[List[Tuple[float, float]], List[int], List[int], List[int]]:
    conn = sqlite3.connect("vrp_data.db")
    cursor = conn.cursor()

    cursor.execute("SELECT latitude, longitude, demand, priority FROM locations")
    locations = [(row[0], row[1]) for row in cursor.fetchall()]
    cursor.execute("SELECT demand FROM locations")
    demands = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT capacity FROM trucks")
    truck_capacities = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT priority FROM locations")
    priorities = [row[0] for row in cursor.fetchall()]

    conn.close()

    locations.insert(0, DEPOT_COORDS)
    demands.insert(0, 0)  
    priorities.insert(0, 0)  
    return locations, demands, truck_capacities, priorities

def update_routing_with_depot():
    try:
        locations, demands, truck_capacities, priorities = read_database_with_depot()

        sorted_locations, sorted_demands = prioritize_locations(locations[1:], demands[1:], priorities[1:])
        locations = [locations[0]] + sorted_locations
        demands = [demands[0]] + sorted_demands

        print("Obteniendo matriz de distancia y tiempo...")
        distance_matrix, time_matrix = get_distance_time_matrix(locations)

        print("Resolviendo VRP...")
        routes = solve_vrp_with_capacity(time_matrix, demands, truck_capacities)

        print("Obteniendo coordenadas para rutas...")
        route_coords = get_route_coordinates(locations, routes)

        print("Generando mapas...")
        drivers = ["Conductor A", "Conductor B", "Conductor C", "Conductor D"]
        individual_maps = generate_individual_maps(
            locations, routes, route_coords, time_matrix, demands, drivers,PRECISE_LOCATION
        )

        map_route = visualize_routes_and_generate_main_map_with_filters(
            locations, DEPOT_COORDS, routes, route_coords, time_matrix, demands, individual_maps,drivers,PRECISE_LOCATION
        )
        map_route.save("rutas_principal.html")
        print("Mapa actualizado: 'rutas_principal.html'")
    except Exception as e:
        print(f"Error durante la actualización de rutas: {e}")

def prioritize_locations(
    locations: List[Tuple[float, float]], 
    demands: List[int], 
    priorities: List[int]
) -> Tuple[List[Tuple[float, float]], List[int]]:
    combined = list(zip(priorities, locations, demands))
    sorted_combined = sorted(combined, reverse=True, key=lambda x: x[0])
    sorted_locations = [loc for _, loc, _ in sorted_combined]
    sorted_demands = [demand for _, _, demand in sorted_combined]
    return sorted_locations, sorted_demands

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

def schedule_updates():
    update_routing_with_depot()
    schedule.every(1).minutes.do(update_routing_with_depot)
    print("Actualizaciones programadas cada 10 minutos.")
    while True:
        schedule.run_pending()
        time.sleep(1)

def generate_individual_maps(
    locations: List[Tuple[float, float]], 
    routes: List[List[int]], 
    all_routes_coords: List[List[Tuple[float, float]]], 
    time_matrix: List[List[float]], 
    demands: List[int],
    drivers: List[str],
    precise_location: Tuple[float, float],
):
    colors = ["blue", "green", "red", "purple", "orange"]
    individual_maps = []

    for vehicle_id, (route, route_coords) in enumerate(zip(routes, all_routes_coords)):
        if len(route) <= 2:
            print(f"Camión {vehicle_id + 1} no tiene rutas asignadas.")
            continue

        color = colors[vehicle_id % len(colors)]
        individual_map = folium.Map(location=locations[0], zoom_start=11)

        folium.Marker(
            precise_location,
            popup="Tu ubicación precisa",
            icon=folium.Icon(color="darkblue", icon="user"),
        ).add_to(individual_map)

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
            <b>Demanda:</b> {demands[node]} unidades<br>
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
    individual_maps: List[Tuple[int, str]],
    drivers: List[str],
    precise_location: Tuple[float, float],
):
    map_route = folium.Map(location=locations[0], zoom_start=11)
    colors = ["blue", "green", "red", "purple", "orange"]

    for vehicle_id, (route, route_coords) in enumerate(zip(routes, all_routes_coords)):
        if len(route) <= 2:
            continue

        color = colors[vehicle_id % len(colors)]
        route_layer = folium.FeatureGroup(name=f"Camión {vehicle_id + 1}", show=True)

        folium.Marker(
            precise_location,
            popup="Tu ubicación precisa",
            icon=folium.Icon(color="darkblue", icon="user"),
        ).add_to(map_route)

        folium.PolyLine(
            route_coords,
            color=color,
            weight=5,
            opacity=0.8,
            tooltip=f"Ruta del Camión {vehicle_id + 1}"
        ).add_to(route_layer)

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
            <b>Camión:</b> {drivers[vehicle_id]}<br>
            <b>Demanda:</b> {demands[node]} unidades<br>
            """

            folium.Marker(
                locations[node],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=color, icon=icon),
            ).add_to(route_layer)

        route_layer.add_to(map_route)

    folium.LayerControl(collapsed=False).add_to(map_route)
    return map_route

def get_precise_location(api_key: str) -> Tuple[float, float]:
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

PRECISE_LOCATION = get_precise_location(api_key="#####")


if __name__ == "__main__":
    schedule_updates()