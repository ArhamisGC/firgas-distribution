import openrouteservice
import folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List, Tuple

ORS_API_KEY = "ClaveApi"
client = openrouteservice.Client(key=ORS_API_KEY)

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
    return routes

def get_route_coordinates(locations: List[Tuple[float, float]], routes: List[List[int]]) -> List[List[Tuple[float, float]]]:
    all_routes_coords = []
    for route in routes:
        route_coords = []
        for i in range(len(route) - 1):
            start = locations[route[i]]
            end = locations[route[i + 1]]
            directions = client.directions(
                coordinates=[[start[1], start[0]], [end[1], end[0]]],
                profile="driving-car",
                format="geojson",
            )
            segment_coords = [(coord[1], coord[0]) for coord in directions["features"][0]["geometry"]["coordinates"]]
            route_coords.extend(segment_coords)
        all_routes_coords.append(route_coords)
    return all_routes_coords

def visualize_routes_with_layer_control(
    locations: List[Tuple[float, float]],
    routes: List[List[int]],
    all_route_coords: List[List[Tuple[float, float]]],
    time_matrix: List[List[float]],
    distance_matrix: List[List[float]],
    demands: List[int]
) -> folium.Map:
    map_route = folium.Map(location=locations[0], zoom_start=11)
    colors = ["blue", "green", "red", "purple", "orange"]

    for vehicle_id, (route, route_coords) in enumerate(zip(routes, all_route_coords)):
        layer = folium.FeatureGroup(name=f"Ruta del Camión {vehicle_id + 1}")

        color = colors[vehicle_id % len(colors)]
        folium.PolyLine(route_coords, color=color, weight=5, opacity=0.8).add_to(layer)

        total_distance = 0
        total_time = 0

        for i, node in enumerate(route[:-1]):
            next_node = route[i + 1]
            distance = distance_matrix[node][next_node]
            time = time_matrix[node][next_node] / 60  
            total_distance += distance
            total_time += time

            folium.Marker(
                locations[node],
                popup=(f"<b>Parada {i + 1}</b><br>"
                       f"Demanda entregada: {demands[node]} unidades<br>"
                       f"Tiempo al siguiente: {time:.1f} min<br>"
                       f"Distancia al siguiente: {distance:.1f} km<br>"
                       f"Distancia total: {total_distance:.1f} km<br>"
                       f"Tiempo total: {total_time:.1f} min"),
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(layer)

        layer.add_to(map_route)

    folium.LayerControl().add_to(map_route)

    return map_route

if __name__ == "__main__":
    central_location = (28.120056, -15.430251)
    locations = [
        central_location,
        (28.073687556995907, -15.451800956382401),
        (27.90184647216374, -15.446392923173903),
        (27.765357123904156, -15.673442527691762),
        (27.808588135553386, -15.483237769536828),
        (27.798971369372776, -15.715452437780161),
        (28.11807130798369, -15.524992806538343),
        (28.132453377326556, -15.66115490051511),
    ]

    demands = [0, 10, 15, 20, 5, 25, 10, 15]  
    vehicle_capacities = [50, 40, 40]  

    print("Obteniendo matriz de distancia y tiempo...")
    distance_matrix, time_matrix = get_distance_time_matrix(locations)

    print("Resolviendo VRP con 3 camiones...")
    routes = solve_vrp_with_capacity(time_matrix, demands, vehicle_capacities)
    route_coords = get_route_coordinates(locations, routes)

    print("Visualizando las rutas con selección por camión...")
    map_route = visualize_routes_with_layer_control(locations, routes, route_coords, time_matrix, distance_matrix, demands)
    map_route.save("rutas_3_camiones_seleccion.html")
    print("Mapa guardado en 'rutas_3_camiones_seleccion.html'. Ábrelo en un navegador.")
