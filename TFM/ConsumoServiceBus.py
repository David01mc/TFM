from azure.servicebus import ServiceBusClient
from pymongo import MongoClient
import json
from dotenv import load_dotenv
import os

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING")

# Configuración de Service Bus
connection_str = os.getenv("SERVICEBUS_CONNECTION_STR")
queue_name = os.getenv("QUEUE_NAME")

# Configuración de MongoDB
mongo_client = MongoClient("CONNECTION_STRING")  # Cambia esto si usas MongoDB en la nube
db = mongo_client["noticias"]  # Base de datos
collection = db["articulos"]  # Colección donde se almacenarán las noticias

def insertar_en_mongo(datos):
    """
    Inserta un documento en MongoDB.
    :param datos: Diccionario con los datos a insertar.
    """
    try:
        collection.insert_one(datos)
        print(f"Insertado en MongoDB: {datos['_id'] if '_id' in datos else 'Sin ID'}")
    except Exception as e:
        print(f"Error al insertar en MongoDB: {e}")

def consumir_desde_servicebus():
    """
    Consume mensajes desde Azure Service Bus y los inserta en MongoDB.
    """
    try:
        with ServiceBusClient.from_connection_string(connection_str) as client:
            receiver = client.get_queue_receiver(queue_name)
            with receiver:
                print(f"Escuchando mensajes desde la cola: {queue_name}")
                for mensaje in receiver:
                    try:
                        # Decodificar el mensaje JSON
                        datos = json.loads(str(mensaje))
                        
                        # Insertar en MongoDB
                        insertar_en_mongo(datos)

                        # Marcar el mensaje como procesado
                        receiver.complete_message(mensaje)
                    except Exception as e:
                        print(f"Error al procesar el mensaje: {e}")
                        receiver.abandon_message(mensaje)  # Devolver a la cola para reprocesar
    except Exception as e:
        print(f"Error al conectar con Service Bus: {e}")

if __name__ == "__main__":
    consumir_desde_servicebus()
