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

# Configurar API de Google Gemini
genai.configure(api_key="AIzaSyDT0aPpY0S6vHRU6CSQMYFbCuToh_ranis")

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

# Configuración de la API de IBM Watson NLU
api_key_ibm = 'n5jofTedHABMfr8STuBm6SjPW409AtuTsuvqcCx1ZsPk'
url_ibm = 'https://api.eu-gb.natural-language-understanding.watson.cloud.ibm.com/instances/da09efb4-b4d5-42fc-a283-db0cc52378d2'

authenticator = IAMAuthenticator(api_key_ibm)
nlu = NaturalLanguageUnderstandingV1(
    version='2021-08-01',
    authenticator=authenticator
)
nlu.set_service_url(url_ibm)


def analizar_sentimiento(comentario):
    """
    Función para analizar el sentimiento de un comentario utilizando Google Gemini.
    
    Parámetros:
    comentario (str): El comentario a analizar.
    
    Retorna:
    dict: Un diccionario con el sentimiento y el porcentaje de confianza.
    """
    try:
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(comentario)
        texto_respuesta = response.text

        # Procesar la respuesta de la API
        if "NEGATIVO" in texto_respuesta:
            sentimiento = "NEGATIVO"
        elif "POSITIVO" in texto_respuesta:
            sentimiento = "POSITIVO"
        else:
            sentimiento = "NEUTRAL"

        # Extraer el porcentaje de confianza
        confianza = int(texto_respuesta.split("Confianza:")[1].strip().replace("%", ""))
        
        return {"sentimiento": sentimiento, "confianza": confianza}
    
    except Exception as e:
        print(f"Error al analizar el comentario: {e}")
        return {"sentimiento": "Indeterminado", "confianza": 0}


def analizar_con_ibm_nlu(texto):
    """
    Función para analizar un texto usando IBM Watson NLU, extrayendo entidades, conceptos, palabras clave, y sentimientos.
    
    Parámetros:
    texto (str): El texto a analizar.
    
    Retorna:
    dict: Diccionario con los resultados del análisis de IBM NLU.
    """
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


def explorar_pagina(url):
    """
    Función para extraer datos de una página web, mostrar artículos, imágenes, autores, subsecciones,
    y luego extraer más información detallada con Selenium de cada noticia. Almacena los datos en un archivo JSON.
    
    Parámetros:
    url (str): URL de la página web que se desea explorar.
    """
    
    # Iniciar el timer
    start_time = time.time()
    
    # Obtener el nombre del dominio de la URL para usarlo en el nombre del archivo
    domain = urlparse(url).netloc.replace('www.', '')

    # Crear el nombre del archivo con la fecha y la hora
    fecha_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{domain}_{fecha_hora}.json"
    
    # Lista para almacenar todos los datos de las noticias
    datos_noticias = []
    
    # Realizar la solicitud GET a la página
    response = requests.get(url)

    # Verificar que la solicitud ha sido exitosa
    if response.status_code == 200:
        # Analizar el contenido HTML de la página
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar todas las secciones con las clases 'module', 'mosaic', 'mosaic-wrapper', 'module recirculation'
        secciones = soup.find_all(['section', 'div'], class_=['module', 'mosaic', 'mosaic-wrapper', 'module recirculation'])
        
        # Variable para almacenar el título de la sección actual
        titulo_seccion_actual = "OTRO"
        
        # Comprobación de que encontramos secciones
        if not secciones:
            print("No se encontraron secciones con las clases 'module', 'mosaic', 'mosaic-wrapper' o 'module recirculation'.")
        
        # Iterar sobre cada sección
        for i, seccion in enumerate(secciones, 1):
            # Intentar encontrar el span con la clase 'title-text-title' para el título de la sección
            span_titulo = seccion.find('span', class_='title-text-title')
            
            # Actualizar el título de la sección solo si encontramos un nuevo span
            if span_titulo:
                titulo_seccion_actual = span_titulo.text.strip()  # Actualizar el título de la sección
            
            # Buscar los artículos dentro de la sección actual
            articles = seccion.find_all('article', class_=['module-text-below-atom', 'module-text-side-atom', 'module-text-over-atom', 'swiper-slide'])
            
            # Verificar si la sección tiene artículos
            if not articles:
                continue  # Si no tiene artículos, pasamos a la siguiente sección
            
            # Mostrar el título actual de la sección
            print(f"\nSección {i}: {titulo_seccion_actual}")
            
            # Extraer los datos de todos los artículos
            for j, article in enumerate(articles, 1):
                print(f"\nArtículo {j} de la Sección '{titulo_seccion_actual}':\n")

                # Diccionario para almacenar los datos de cada artículo
                articulo_data = {}

                # Titular de la noticia
                titular_tag = article.find('a', class_='media') or article.find('a', class_='image')
                if titular_tag:
                    titular = titular_tag.get('title')
                    url_noticia = titular_tag.get('href')
                    print(f"Titular: {titular}")
                    print(f"URL a la noticia: {url_noticia}")

                    # Almacenar en el diccionario
                    articulo_data['titular'] = titular
                    articulo_data['url_noticia'] = url_noticia

                    # Procesar solo los enlaces que terminan en .html
                    if url_noticia and url_noticia.endswith('.html'):
                        # Aquí llamamos a la función que usa Selenium para extraer más detalles
                        detalles_noticia = extraer_datos_selenium(url_noticia)
                        articulo_data.update(detalles_noticia)

                        # Extraer las noticias relacionadas (aside related-content)
                        related_content = article.find('aside', class_='related-content')
                        if related_content:
                            relacionados = []
                            for related in related_content.find_all('a'):
                                related_title = related.find('h2', class_='subtitle-atom').text.strip() if related.find('h2', class_='subtitle-atom') else "Sin título"
                                related_url = related['href']
                                relacionados.append({
                                    "titulo_relacionado": related_title,
                                    "url_relacionada": related_url
                                })
                            articulo_data['noticias_relacionadas'] = relacionados
                        else:
                            articulo_data['noticias_relacionadas'] = []

                # Añadir los datos del artículo a la lista principal
                datos_noticias.append(articulo_data)

    else:
        print(f"Error al acceder a la página. Código de estado: {response.status_code}")
    
    # Guardar los datos extraídos en un archivo JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(datos_noticias, f, ensure_ascii=False, indent=4)
    
    print(f"\nDatos guardados en el archivo '{output_file}'.")

    # Mostrar el tiempo que tardó el proceso
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Tiempo total de extracción: {elapsed_time:.2f} segundos")


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

#==========================================================================
#    Ejecutamos la funcion, comprbando que se ha proporcionado una URL
#==========================================================================

import sys

# Comprobar si se ha proporcionado una URL como argumento
if len(sys.argv) > 1:
    url_to_explore = sys.argv[1]
else:
    # Si no se proporciona ninguna URL, usar una URL predeterminada
    url_to_explore = "https://www.diariodecadiz.es/"

# Llamar a la función con la URL proporcionada
explorar_pagina(url_to_explore)

