import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import json
import time
import os
from datetime import datetime
from urllib.parse import urlparse
import google.generativeai as genai
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 import Features, EntitiesOptions, KeywordsOptions, ConceptsOptions, SentimentOptions
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from pymongo import MongoClient  # Importación para la conexión con Azure Cosmos DB

from dotenv import load_dotenv
import os

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
    """
    Función para abrir una noticia en Selenium, hacer scroll, aceptar cookies y extraer datos como JSON-LD y comentarios.
    
    Parámetros:
    url_noticia (str): URL de la noticia que se va a procesar.

    Retorna:
    dict: Diccionario con los datos extraídos de la noticia.
    """
    # Usamos las rutas establecidas en el contenedor
    CHROME_DRIVER_PATH = "/usr/bin/chromedriver"

    # Configurar el servicio de ChromeDriver
    service = Service(CHROME_DRIVER_PATH)

    # Opciones para ejecutar Chrome en modo headless
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Ejecutar en modo sin interfaz gráfica
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.binary_location = "/usr/bin/chromium"  # Ruta para el navegador

    # Iniciar el navegador
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Abrir la página
    driver.get(url_noticia)

    # Esperar unos segundos para que el botón de "Aceptar y continuar" se cargue
    time.sleep(0.7)

    # Intentar encontrar y hacer clic en el botón de "Aceptar y continuar"
    try:
        aceptar_boton = driver.find_element(By.CSS_SELECTOR, 'a.mrf-button[data-mrf-role="userAgreeToAll"]')
        aceptar_boton.click()
        print("Botón 'Aceptar y continuar' clicado.")
    except:
        print("No se encontró el botón 'Aceptar y continuar'.")

    # Esperar un segundo para que la página cargue completamente después de aceptar
    time.sleep(0.7)

    # Hacer scroll tres veces
    for i in range(3):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(0.5)  # Esperar un segundo entre cada scroll para que el contenido se cargue

    # Obtener el código fuente de la página después de cargar y hacer scroll
    page_source = driver.page_source

    # Analizar el contenido HTML con BeautifulSoup
    soup = BeautifulSoup(page_source, 'html.parser')

    # Diccionario para almacenar los datos de la noticia
    datos_noticia = {}

    # Buscar el script con type="application/ld+json"
    ld_json_script = soup.find('script', {'type': 'application/ld+json'})

    if ld_json_script:
        # Parsear el contenido JSON
        ld_json_content = json.loads(ld_json_script.string)
        
        # Acceder a la información dentro del JSON
        datos_noticia['headline'] = ld_json_content.get('headline')
        datos_noticia['url'] = ld_json_content.get('url')
        
        # Manejar si 'image' es un string o un objeto
        image = ld_json_content.get('image')
        if isinstance(image, str):
            datos_noticia['image_url'] = image
            datos_noticia['image_name'] = ''
        elif isinstance(image, dict):
            datos_noticia['image_url'] = image.get('url')
            datos_noticia['image_name'] = image.get('name')

        datos_noticia['author'] = ld_json_content.get('author', [{}])[0].get('name')
        datos_noticia['date_published'] = ld_json_content.get('datePublished')
        datos_noticia['date_modified'] = ld_json_content.get('dateModified')
        datos_noticia['publisher'] = ld_json_content.get('publisher', {}).get('name')
        datos_noticia['article_section'] = ld_json_content.get('articleSection', [])
        datos_noticia['description'] = ld_json_content.get('description')
        datos_noticia['article_body'] = ld_json_content.get('articleBody')
        datos_noticia['keywords'] = ld_json_content.get('keywords', [])
        datos_noticia['content_location'] = ld_json_content.get('contentLocation', [{}])[0].get('name')

        # Análisis del artículo con IBM Watson NLU
        analisis_nlu = analizar_con_ibm_nlu(datos_noticia['article_body'])
        datos_noticia['analisis_nlu'] = analisis_nlu

    else:
        print("No se encontró el script con el tipo 'application/ld+json'.")

    # Intentar obtener los comentarios y agregar la información
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
                
                # Análisis de sentimiento usando Gemini
                analisis_sentimiento = analizar_sentimiento(comentario_data['texto_comentario'])
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
    Función para extraer datos de una página web, mostrar artículos, imágenes, autores, subsecciones,
    y luego extraer más información detallada con Selenium de cada noticia. Almacena los datos en un archivo JSON.
    Además, envía los datos extraídos a Azure Cosmos DB.
    
    Parámetros:
    url (str): URL de la página web que se desea explorar.
    """
    start_time = time.time()
    domain = urlparse(url).netloc.replace('www.', '')
    datos_noticias = []

    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        secciones = soup.find_all(['section', 'div'], class_=['module', 'mosaic', 'mosaic-wrapper', 'module recirculation'])

        titulo_seccion_actual = "OTRO"
        for i, seccion in enumerate(secciones[:3], 1):  # Procesa solo las 3 primeras noticias
            span_titulo = seccion.find('span', class_='title-text-title')
            if span_titulo:
                titulo_seccion_actual = span_titulo.text.strip()

            articles = seccion.find_all('article', class_=['module-text-below-atom', 'module-text-side-atom', 'module-text-over-atom', 'swiper-slide'])
            if not articles:
                continue

            for article in articles[:3]:  # Limita el procesamiento de noticias individuales
                articulo_data = {}
                titular_tag = article.find('a', class_='media') or article.find('a', class_='image')
                if titular_tag:
                    titular = titular_tag.get('title')
                    url_noticia = titular_tag.get('href')

                    articulo_data['titular'] = titular
                    articulo_data['url_noticia'] = url_noticia

                    if url_noticia and url_noticia.endswith('.html'):
                        detalles_noticia = extraer_datos_selenium(url_noticia)
                        articulo_data.update(detalles_noticia)
                datos_noticias.append(articulo_data)

    else:
        print(f"Error al acceder a la página. Código de estado: {response.status_code}")

    collection_name = extraer_nombre_de_coleccion(url)
    collection = conectar_a_cosmos(CONNECTION_STRING, DATABASE_NAME, collection_name)
    if collection is not None:  # Comparación explícita con None
        insertar_datos(collection, datos_noticias)

    end_time = time.time()
    print(f"Tiempo total de extracción: {end_time - start_time:.2f} segundos")



if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        url_to_explore = sys.argv[1]
    else:
        url_to_explore = "https://www.diariodecadiz.es/"

    explorar_pagina(url_to_explore)
