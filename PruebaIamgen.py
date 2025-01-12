import requests

# Datos de configuración
subscription_key = "2xbRH8BEJ435TXmeu01EkDbWE3gyVLcKWucq8jRTObiu8w5d03aBJQQJ99AJACYeBjFXJ3w3AAAFACOGdy6y"
endpoint = "https://pruebaapimaster.cognitiveservices.azure.com/"
analyze_url = f"{endpoint}vision/v3.2/analyze"

# Parámetros de la solicitud: incluir varias funcionalidades
params = {
    "visualFeatures": "Description,Tags,Objects,Color,Brands",  # Pedimos múltiples características
    "language": "es"  # Salida en español
}

# URL de la imagen
image_url = "https://static.grupojoly.com/clip/f6c2a109-fe69-4990-80dc-65b5fedbd59b_source-aspect-ratio_1600w_0.jpg"

# Cabeceras de la solicitud
headers = {
    "Ocp-Apim-Subscription-Key": subscription_key,
    "Content-Type": "application/json"
}

# Cuerpo de la solicitud
data = {
    "url": image_url
}

# Realizar la solicitud
response = requests.post(analyze_url, headers=headers, params=params, json=data)
response.raise_for_status()

# Procesar la respuesta
analysis = response.json()

# Extraer y mostrar resultados
print("== Análisis de la Imagen ==")

# Descripción
description = analysis.get("description", {}).get("captions", [{}])[0].get("text", "No disponible")
print(f"Descripción: {description}")

# Etiquetas
tags = analysis.get("tags", [])
print("\nEtiquetas:")
for tag in tags:
    print(f" - {tag['name']} (confianza: {tag['confidence']:.2f})")

# Objetos detectados
objects = analysis.get("objects", [])
print("\nObjetos detectados:")
for obj in objects:
    print(f" - {obj['object']} (coordenadas: {obj['rectangle']})")

# Esquema de colores
color_info = analysis.get("color", {})
