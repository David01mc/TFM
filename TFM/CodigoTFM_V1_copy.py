import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import json
import time
from datetime import datetime
from urllib.parse import urlparse
import google.generativeai as genai
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 import Features, EntitiesOptions, KeywordsOptions, ConceptsOptions, SentimentOptions
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from pymongo import MongoClient  # Importación para la conexión con Azure Cosmos DB
from dotenv import load_dotenv
import os
from azure.servicebus import ServiceBusClient, ServiceBusMessage

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Acceder a las claves desde las variables de entorno
AZURE_SUBSCRIPTION_KEY = os.getenv("AZURE_SUBSCRIPTION_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_ANALYZE_URL = f"{AZURE_ENDPOINT}vision/v3.2/analyze"

API_KEY = os.getenv("AZURE_TEXT_ANALYTICS_KEY")
ENDPOINT = os.getenv("AZURE_TEXT_ANALYTICS_ENDPOINT")
SENTIMENT_URL = f"{ENDPOINT}text/analytics/v3.1/sentiment"

GENAI_API_KEY = os.getenv("GENAI_API_KEY")

IBM_API_KEY = os.getenv("IBM_API_KEY")
IBM_URL = os.getenv("IBM_URL")

CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING")
DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME")

# Configurar modelo de análisis de sentimientos
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Crear modelo para análisis de sentimientos
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction="Tu tarea será categorizar comentarios en Positivo, Negativo o Neutral, añadiendo un porcentaje de confianza. No hace falta que digas nada más. Ejemplo: NEGATIVO Confianza: 95%",
)

authenticator = IAMAuthenticator(IBM_API_KEY)
nlu = NaturalLanguageUnderstandingV1(
    version='2021-08-01',
    authenticator=authenticator
)
nlu.set_service_url(IBM_URL)

connection_str = os.getenv("SERVICEBUS_CONNECTION_STR")
queue_name = os.getenv("QUEUE_NAME")

def enviar_a_servicebus(mensaje):
    with ServiceBusClient.from_connection_string(connection_str) as client:
        sender = client.get_queue_sender(queue_name)
        with sender:
            sender.send_messages(ServiceBusMessage(mensaje))
            print("Mensaje enviado a Service Bus.")

def analizar_sentimiento_azure(texto):
    """
    Analiza el sentimiento de un texto usando Azure Text Analytics.
    """
    try:
        headers = {
            "Ocp-Apim-Subscription-Key": API_KEY,
            "Content-Type": "application/json"
        }

        # El cuerpo de la solicitud debe incluir los textos a analizar
        body = {
            "documents": [
                {"id": "1", "language": "es", "text": texto}
            ]
        }

        # Realizar la solicitud a la API
        response = requests.post(SENTIMENT_URL, headers=headers, json=body)
        response.raise_for_status()  # Lanza una excepción si la solicitud falla
        result = response.json()

        # Procesar los resultados
        if "documents" in result and len(result["documents"]) > 0:
            sentiment_data = result["documents"][0]
            return {
                "sentimiento": sentiment_data["sentiment"],  # "positive", "neutral", o "negative"
                "confianza": sentiment_data["confidenceScores"]  # Scores para cada sentimiento
            }
        else:
            return {
                "sentimiento": "indeterminado",
                "confianza": {}
            }
    except Exception as e:
        print(f"Error al analizar el sentimiento: {e}")
        return {
            "sentimiento": "error",
            "confianza": {}
        }

def analizar_imagen_azure(image_url):
    """
    Realiza una solicitud a la API de Azure Computer Vision para analizar una imagen.
    Devuelve una descripción y las 5 etiquetas principales de la imagen.
    """
    try:
        # Parámetros para la API de Azure
        params = {
            "visualFeatures": "Description,Tags",  # Pedir descripción y etiquetas
            "language": "es"  # Salida en español
        }
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SUBSCRIPTION_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "url": image_url
        }

        # Realizar solicitud a Azure
        response = requests.post(AZURE_ANALYZE_URL, headers=headers, params=params, json=data)
        response.raise_for_status()
        analysis = response.json()

        # Obtener la descripción
        descripcion = analysis.get("description", {}).get("captions", [{}])[0].get("text", "No disponible")
        confianza_descripcion = analysis.get("description", {}).get("captions", [{}])[0].get("confidence", 0)

        # Obtener las 5 etiquetas principales
        tags = analysis.get("tags", [])
        top_tags = sorted(tags, key=lambda t: t["confidence"], reverse=True)[:5]

        etiquetas = [{"etiqueta": tag["name"], "confianza": tag["confidence"]} for tag in top_tags]

        # Devolver resultados
        return {
            "descripcion": descripcion,
            "confianza_descripcion": confianza_descripcion,
            "etiquetas": etiquetas
        }
    except Exception as e:
        print(f"Error al analizar la imagen con Azure: {e}")
        return {
            "descripcion": "Error",
            "confianza_descripcion": 0,
            "etiquetas": []
        }

def conectar_a_cosmos(connection_string, db_name, collection_name):
    try:
        client = MongoClient(connection_string)
        db = client[db_name]
        print(f"Conectado a la base de datos: {db_name}")

        if collection_name not in db.list_collection_names():
            print(f"La colección '{collection_name}' no existe. Creándola...")
            db.create_collection(collection_name)
        else:
            print(f"La colección '{collection_name}' ya existe.")

        return db[collection_name]
    except Exception as e:
        print(f"Error al conectar a Cosmos DB: {e}")
        return None

def insertar_datos(collection, datos):
    try:
        if isinstance(datos, list):
            collection.insert_many(datos)
            print("Datos insertados con éxito en la colección.")
        else:
            collection.insert_one(datos)
            print("Documento insertado con éxito en la colección.")
    except Exception as e:
        print(f"Error al insertar datos: {e}")

def extraer_nombre_de_coleccion(url):
    domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
    return domain

def analizar_sentimiento(comentario):
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(comentario)
        texto_respuesta = response.text

        if "NEGATIVO" in texto_respuesta:
            sentimiento = "NEGATIVO"
        elif "POSITIVO" in texto_respuesta:
            sentimiento = "POSITIVO"
        else:
            sentimiento = "NEUTRAL"

        confianza = int(texto_respuesta.split("Confianza:")[1].strip().replace("%", ""))
        return {"sentimiento": sentimiento, "confianza": confianza}
    except Exception as e:
        print(f"Error al analizar el comentario: {e}")
        return {"sentimiento": "Indeterminado", "confianza": 0}

def analizar_con_ibm_nlu(texto):
    try:
        response = nlu.analyze(
            text=texto,
            features=Features(
                entities=EntitiesOptions(sentiment=True, limit=5),
                keywords=KeywordsOptions(sentiment=True, limit=5),
                concepts=ConceptsOptions(limit=5),
                sentiment=SentimentOptions()
            )
        ).get_result()

        return response
    except Exception as e:
        print(f"Error al analizar el texto con IBM NLU: {e}")
        return {}

def extraer_datos_selenium(url_noticia):
    CHROME_DRIVER_PATH = "chromedriver.exe"
    service = Service(CHROME_DRIVER_PATH)
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(url_noticia)
    time.sleep(0.7)

    try:
        aceptar_boton = driver.find_element(By.CSS_SELECTOR, 'a.mrf-button[data-mrf-role="userAgreeToAll"]')
        aceptar_boton.click()
        print("Botón 'Aceptar y continuar' clicado.")
    except Exception as e:
        print("No se encontró el botón 'Aceptar y continuar':", e)

    time.sleep(0.7)
    for i in range(3):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(0.5)

    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    datos_noticia = {}

    ld_json_script = soup.find('script', {'type': 'application/ld+json'})
    if ld_json_script:
        ld_json_content = json.loads(ld_json_script.string)
        datos_noticia = {
            'headline': ld_json_content.get('headline'),
            'url': ld_json_content.get('url'),
            'image_url': ld_json_content.get('image', {}).get('url') if isinstance(ld_json_content.get('image'), dict) else ld_json_content.get('image'),
            'author': ld_json_content.get('author', [{}])[0].get('name'),
            'date_published': ld_json_content.get('datePublished'),
            'date_modified': ld_json_content.get('dateModified'),
            'publisher': ld_json_content.get('publisher', {}).get('name'),
            'article_section': ld_json_content.get('articleSection', []),
            'description': ld_json_content.get('description'),
            'article_body': ld_json_content.get('articleBody'),
            'keywords': ld_json_content.get('keywords', []),
        }
        datos_noticia['analisis_nlu'] = analizar_con_ibm_nlu(datos_noticia['article_body'])

    # Si hay una imagen asociada, analiza la imagen con Azure
    image_url_data = datos_noticia.get('image_url')

    if image_url_data:
        if isinstance(image_url_data, list):  # Si es una lista de objetos
            # Busca el primer objeto con una URL válida
            for image_object in image_url_data:
                if isinstance(image_object, dict) and 'url' in image_object:
                    image_url = image_object['url']
                    break
            else:
                image_url = None  # Ninguna URL válida encontrada
        elif isinstance(image_url_data, dict):  # Si es un único objeto
            image_url = image_url_data.get('url', None)
        else:  # Si no es ni lista ni dict
            image_url = image_url_data

        if image_url:  # Si se encontró una URL válida
            datos_noticia['image_analysis'] = analizar_imagen_azure(image_url)
        else:
            print("No se encontró una URL de imagen válida.")
    else:
        print("El campo 'image_url' no está presente o está vacío.")

    try:
        comentarios = driver.find_elements(By.CLASS_NAME, 'comment')
        lista_comentarios = []
        if comentarios:
            for comentario in comentarios:
                comentario_data = {}
                # Nombre del usuario
                comentario_data['nombre'] = comentario.find_element(By.CLASS_NAME, 'comment-info-name').text
                # Tiempo de publicación
                comentario_data['tiempo'] = comentario.find_element(By.CLASS_NAME, 'comment-info-date').text
                # Texto del comentario
                comentario_data['texto_comentario'] = comentario.find_element(By.CLASS_NAME, 'comment-info-text').text

                # Análisis de sentimiento usando Azure Text Analytics
                analisis_sentimiento = analizar_sentimiento_azure(comentario_data['texto_comentario'])
                comentario_data.update(analisis_sentimiento)

                # Agregar comentario al listado
                lista_comentarios.append(comentario_data)
            datos_noticia['comentarios'] = lista_comentarios
        else:
            datos_noticia['comentarios'] = []
    except Exception as e:
        print(f"Error al intentar obtener los comentarios: {e}")


    # Cerrar el navegador
    driver.quit()
    return datos_noticia

# Ajustar `explorar_pagina` para limitar el número de noticias procesadas

def explorar_pagina(url):
    """
    Función para extraer datos de una página web y procesar cada noticia de manera individual.
    Envía cada noticia como un JSON único.
    """
    start_time = time.time()
    domain = urlparse(url).netloc.replace('www.', '')
    
    # Realiza la solicitud a la página principal
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error al acceder a la página. Código de estado: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    secciones = soup.find_all(['section', 'div'], class_=['module', 'mosaic', 'mosaic-wrapper', 'module recirculation'])

    for i, seccion in enumerate(secciones[:3], 1):  # Procesa solo las 3 primeras secciones
        span_titulo = seccion.find('span', class_='title-text-title')
        titulo_seccion_actual = span_titulo.text.strip() if span_titulo else "OTRO"

        articles = seccion.find_all('article', class_=['module-text-below-atom', 'module-text-side-atom', 'module-text-over-atom', 'swiper-slide'])
        if not articles:
            continue

        for article in articles[:3]:  # Procesa solo las 3 primeras noticias por sección
            articulo_data = {}

            # Extraer URL y título de la noticia
            titular_tag = article.find('a', class_='media') or article.find('a', class_='image')
            if titular_tag:
                articulo_data['titular'] = titular_tag.get('title')
                articulo_data['url_noticia'] = titular_tag.get('href')

                if articulo_data['url_noticia'] and articulo_data['url_noticia'].endswith('.html'):
                    # Extraer detalles de la noticia
                    detalles_noticia = extraer_datos_selenium(articulo_data['url_noticia'])
                    articulo_data.update(detalles_noticia)

                    # Enviar cada noticia como un JSON único a Service Bus
                    enviar_a_servicebus(json.dumps(articulo_data))  # Enviamos directamente a Service Bus
                    print(f"Noticia enviada a Service Bus: {articulo_data['titular']}")

    end_time = time.time()
    print(f"Tiempo total de extracción: {end_time - start_time:.2f} segundos")



if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        url_to_explore = sys.argv[1]
    else:
        url_to_explore = "https://www.diariodecadiz.es/"

    explorar_pagina(url_to_explore)
