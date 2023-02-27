# coding=utf-8
#!/usr/bin/env python3

import socket
import selectors    #https://docs.python.org/3/library/selectors.html
import select
import types        # Para definir el tipo de datos data
import argparse     # Leer parametros de ejecución
import os           # Obtener ruta y extension
from datetime import datetime, timedelta # Fechas de los mensajes HTTP
import time         # Timeout conexión
import sys          # sys.exit
import re           # Analizador sintáctico
import logging      # Para imprimir logs



BUFSIZE = 8192 # Tamaño máximo del buffer que se puede utilizar
#XXYY = 3776 -> Nombre de la organización: STTT3776.org
TIMEOUT_CONNECTION = 23 # Timeout para la conexión persistente = 3+7+7+6 = 23
MAX_ACCESOS = 10# Número máximo de accesos a la página index.html
HTTP_REGEX = re.compile(r'[^ ]{3,} [^ ]+ HTTP/[0-9].*\r\n(.+: .+\r\n)*\r\n(.*\n?)*')
ALVARO_EMAIL = "a.navarromartinez1@um.es"
GERMAN_EMAIL = "german.sanchez2@um.es"
OK_FILE = "ok_file.html"
FAIL_FILE = "failed_file.html"

# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif":"image/gif", "jpg":"image/jpg", "jpeg":"image/jpeg", "png":"image/png", "htm":"text/htm", 
             "html":"text/html", "css":"text/css", "js":"text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()


def enviar_mensaje(cs, data):
    """ Esta función envía datos (data) a través del socket cs
        Devuelve el número de bytes enviados.
    """
    #comprobamos el tamaño del mensaje 
    if len(data) > BUFSIZE:
        #dividimos el mensaje en trozos de 8192
        trozos = [data[i:i+BUFSIZE] for i in range(0, len(data), BUFSIZE)]

        #enviamos los trozos
        for trozo in trozos:
            cs.send(trozo)
    else:
        cs.send(data)

def crear_cabeceras_HTTP(content_type, content_length, cookie_counter):
    """ Esta función construye las cabeceras HTTP
        Devuelve las cabeceras HTTP
    """
    response = ("Date: " + datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT") + "\r\n"
        + "Server: STTT3776.org\r\n"
        + "Connection: keep-alive\r\n"
        + "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + "\r\n")
    
    if cookie_counter != 0:
        response += ("Set-Cookie: cookie_counter_3776=" + str(cookie_counter) + "; "
        + "max-age=120\r\n")
                
    response += ("Content-Length: " + str(content_length) + "\r\n"
        + "Content-Type: " + filetypes[content_type] + "\r\n")
    
    return response

def crear_mensaje_error(code, msg, cookie_counter, mode, file):
    """ Esta función construye un mensaje de error HTTP
        Devuelve el mensaje de error
    """
    html_error = ("<!DOCTYPE html>"
        + "<html>\r\n"
        +   "\t<head>\r\n"
        +       "\t\t<title>Error "+str(code)+"</title>\r\n"
        +   "\t</head>\r\n"
        +   "\t<body>\r\n"
        +       "\t\t<h1>"+str(code)+". "+msg+"</h1>\r\n"
        +   "\t</body>\r\n"
        + "</html>\r\n")
    
    if mode == 0:
        response = ("HTTP/1.1 " + str(code) + " " + msg + "\r\n"
            + crear_cabeceras_HTTP("html", len(FAIL_FILE), cookie_counter)
            + "\r\n" 
            + html_error)
    elif mode == 1:
        response = ("HTTP/1.1 " + str(code) + " " + msg + "\r\n"
            + crear_cabeceras_HTTP("html", os.path.getsize(file), cookie_counter)
            + "\r\n")
    
    return response.encode("utf-8")

def crear_mensaje_ok(content_type, content_length, cookie_counter):
    """ Esta función construye un mensaje de respuesta HTTP 200 OK
        Devuelve el mensaje de respuesta
    """
    return ("HTTP/1.1 200 OK\r\n" 
        + crear_cabeceras_HTTP(content_type, content_length, cookie_counter) 
        + "\r\n").encode("utf-8")

def recibir_mensaje(cs):
    """ Esta función recibe datos a través del socket cs
        Leemos la información que nos llega. recv() devuelve un string con los datos.
    """
    data = ""
    while True:
        aux = cs.recv(BUFSIZE).decode("utf-8")
        data += aux
        if len(aux) < BUFSIZE:
            break
    return data


def cerrar_conexion(cs):
    """ Esta función cierra una conexión activa.
    """
    cs.close()


def process_cookies(headers, url):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    cookie_counter = 0
    #Recorremos las cabeceras y analizamos para ver si se trata de cookie counter
    for head in headers:
        #imprimimos la cabecera
        print(head)

        aux = head.split(":")
        #Analizamos si se trata de cookie counter
        if aux[0] == "Cookie" and aux[1].split("=")[0] == " cookie_counter_3776":
            cookie_counter = int(head.split("=")[1])

            #comprobamos si se pide el index para aumentar el contador
            if url != "index.html":
                return cookie_counter

            #comprobamos si el valor es MAX_ACCESOS
            if cookie_counter == MAX_ACCESOS:
                return MAX_ACCESOS
            return cookie_counter+1
    #Si no hay cabecera Cookie se devuelve 1 
    return cookie_counter+1


    

def is_method_http(method):
    """ Esta función comprueba si el método está incluido
        en la lista de métodos admitidos por nuestro servidor.
    """
    return method in ["GET", "POST"]

def process_get_request(cs, _url, webroot, headers):
    """ Esta función procesa una petición GET
        1. Se comprueba si el fichero solicitado existe
        2. Si no existe se envía un mensaje de error 404
        3. Si existe se envía el fichero solicitado
    """
    #leemos la url y eliminamos parametros
    url = _url.split('?')[0]

    #comprobamos si el recurso solicitado es /
    if url == "/":
        url = "index.html"
    elif url[0] == "/" and webroot.endswith("/"): #eliminamos la barra inicial
        url = url.split("/")[1]

    #construimos la ruta absoluta del recurso
    path = webroot + url

    #procesamos las cookies
    cookie_counter = process_cookies(headers, url)
    if cookie_counter == MAX_ACCESOS:
        print("Error 403: Forbidden\n\n")
        enviar_mensaje(cs, crear_mensaje_error(403, "Forbidden", cookie_counter, 0, ""))
        return -1

    #compobamos que el recurso existe
    if not os.path.isfile(path):
        print("Error 404: Not Found\n\n")
        enviar_mensaje(cs, crear_mensaje_error(404, "Not Found", cookie_counter, 0, ""))
        return 0

    #obtener el tamaño del recurso en bytes
    size = os.path.getsize(path)

    #extraer la extension para obtener el tipo de archivo
    extension = url.split('.')[1]

    #preparamos la respuesta con codigo 200
    response = crear_mensaje_ok(extension, size, cookie_counter)

    #leer y enviar el contenido del fichero pedido
    # 1. Abrir el fichero en modo lectura y binario
    with open(path, 'rb') as f:
        # 2. Leer el fichero en bloques de BUFSIZE bytes
        while True:
            trozo = f.read(BUFSIZE)

            # 3. Añadir a la respuesta el trozo leído
            response += trozo
            
            if not trozo:
                break  # No hay más información para leer

    #enviamos la respuesta
    enviar_mensaje(cs, response)

def process_post_request(cs, lines, webroot, headers):
    ''' Esta función procesa una petición POST
        1. Comprobamos el email introducido
        2. Si el email es correcto se envía el fichero ok.html
    '''
    #obtenemos el email
    email = lines[0].split('=')[1]

    #comprobamos si el email contiene el caracter %40 que es el @
    if "%40" in email:
        email = email.replace('%40', '@')
    
    #comprobamos si el email introducido es correcto y actuamos en consecuencia
    ok = email == ALVARO_EMAIL or email == GERMAN_EMAIL
    if ok:
        file = webroot + OK_FILE
    else: 
        file = webroot + FAIL_FILE

    #procesamos las cookies
    cookie_counter = process_cookies(headers, "")

    #obtenemos tamaño del fichero
    size = os.path.getsize(file)

    #preparamos la respuesta
    if ok:
        response = crear_mensaje_ok("html", size, cookie_counter)
    else:
        print("Error 401: Unauthorized\n\n")
        response = crear_mensaje_error(401, "Unauthorized", cookie_counter, 1, file)

    #Leemos el fichero (que no tiene más de 8 KB)
    with open(file, 'rb') as f:
        response += f.read(BUFSIZE)

    #enviamos el mensaje
    print("---\n",response.decode('utf-8'),"\n---")
    enviar_mensaje(cs, response)

def process_web_request(cs, webroot):
    """ Procesamiento principal de los mensajes recibidos.
        Típicamente se seguirá un procedimiento similar al siguiente (aunque el alumno puede modificarlo si lo desea)

        * Bucle para esperar hasta que lleguen datos en la red a través del socket cs con select()

            * Se comprueba si hay que cerrar la conexión por exceder TIMEOUT_CONNECTION segundos
              sin recibir ningún mensaje o hay datos. Se utiliza select.select

            * Si no es por timeout y hay datos en el socket cs.
                * Leer los datos con recv.
                * Analizar que la línea de solicitud y comprobar está bien formateada según HTTP 1.1
                    * Devuelve una lista con los atributos de las cabeceras.
                    * Comprobar si la versión de HTTP es 1.1
                    * Comprobar si es un método GET. Si no devolver un error Error 405 "Method Not Allowed".
                    * Leer URL y eliminar parámetros si los hubiera
                    * Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html
                    * Construir la ruta absoluta del recurso (webroot + recurso solicitado)
                    * Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found"
                    * Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
                      el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS.
                      Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
                    * Obtener el tamaño del recurso en bytes.
                    * Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type
                    * Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
                      las cabeceras Date, Server, Connection, Set-Cookie (para la cookie cookie_counter),
                      Content-Length y Content-Type.
                    * Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
                    * Se abre el fichero en modo lectura y modo binario
                        * Se lee el fichero en bloques de BUFSIZE bytes (8KB)
                        * Cuando ya no hay más información para leer, se corta el bucle

            * Si es por timeout, se cierra el socket tras el período de persistencia.
                * NOTA: Si hay algún error, enviar una respuesta de error con una pequeña página HTML que informe del error.
    """
    
    data = ""
    #bucle para esperar hasta que lleguen datos en la red 
    while True:
        #Esperamos solicitud del cliente
        rsublist, wsublist, xsublist = select.select([cs], [], [], TIMEOUT_CONNECTION)

        #comprobamos timeout excedido
        if not rsublist:
            print("-- Timeout excedido. Cerrando conexion")
            cerrar_conexion(cs)
            return

        #Si hay datos en rsublist y timeout no excedido
        if cs in rsublist:
            mensaje = recibir_mensaje(cs)
            if not mensaje: #cliente ha cerrado la conexion
                print("-- Cliente ha cerrado la conexion")
                cerrar_conexion(cs)
                return
            data += mensaje

        if data == "":
            print("-- Error al recibir datos. Cerrando conexion")
            cerrar_conexion(cs)
            return

        if not data.endswith("\r\n\r\n") and not data.startswith("POST"):
            continue

        rsublist = [] #limpiamos la lista
        aux = data
        data = "" #limpiamos la variable 

        print("\n")
        #analizamos la linea de solicitud
        if not re.fullmatch(HTTP_REGEX, aux):
            print("Error 400: Bad Request\n\n")
            enviar_mensaje(cs, crear_mensaje_error(400, "Bad Request", 0, 0, ""))
            continue
        print("-- Peticion bien formateada segun HTTP 1.1")
        
        lines = aux.split('\r\n')

        #obtenemos las cabeceras
        headers = []
        i=1
        while lines[i]:
            if lines[i].startswith("Host:"):
                print("-- Detectada cabecera Host: ", lines[i].split(' ')[1])
            headers.append(lines[i])
            i=i+1

        #obtenemos la linea de solicitud dividida
        req = lines[0].split(' ') # req = [method, url, vesion]
        print("req=",req)
        
        if req[2] != "HTTP/1.1": #comprobar version
            print("Error 505: Version Not Supported\n\n")
            enviar_mensaje(cs, crear_mensaje_error(505, "Version Not Supported", 0, 0, "")) 
            continue
        print("-- Version HTTP 1.1")
        
        if not is_method_http(req[0]): #comprobar si es un metodo valido
            print("Error 405: Method Not Allowed\n\n")
            enviar_mensaje(cs, crear_mensaje_error(405, "Method Not Allowed", 0, 0, ""))
            continue

        if req[0] == "GET":
            error_code = process_get_request(cs, req[1], webroot, headers)
            if error_code == -1:
                cerrar_conexion(cs)
                return 
            elif error_code == 0:
                continue

        if req[0] == "POST" and req[1] == "/accion_form.html":
            if process_post_request(cs, lines[i+1:len(lines)], webroot, headers) == -1:
                continue

        print("^^^Peticion correcta^^^\n\n")



def main():
    """ Función principal del servidor
    """

    try:

        # Argument parser para obtener la ip y puerto de los parámetros de ejecución del programa. IP por defecto 0.0.0.0
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--port", help="Puerto del servidor", type=int, required=True)
        parser.add_argument("-ip", "--host", help="Dirección IP del servidor o localhost", required=True)
        parser.add_argument("-wb", "--webroot", help="Directorio base desde donde se sirven los ficheros (p.ej. /home/user/mi_web)")
        parser.add_argument('--verbose', '-v', action='store_true', help='Incluir mensajes de depuración en la salida')
        args = parser.parse_args()


        if args.verbose:
            logger.setLevel(logging.DEBUG)

        logger.info('Enabling server in address {} and port {}.'.format(args.host, args.port))

        logger.info("Serving files from {}".format(args.webroot))

        """ Funcionalidad a realizar
        * Crea un socket TCP (SOCK_STREAM)
        * Permite reusar la misma dirección previamente vinculada a otro proceso. Debe ir antes de sock.bind
        * Vinculamos el socket a una IP y puerto elegidos

        * Escucha conexiones entrantes

        * Bucle infinito para mantener el servidor activo indefinidamente
            - Aceptamos la conexión

            - Creamos un proceso hijo

            - Si es el proceso hijo se cierra el socket del padre y procesar la petición con process_web_request()

            - Si es el proceso padre cerrar el socket que gestiona el hijo.
        """
        #Creamos un socket
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, proto=0)
        
        #reusamos la dirección previamente vinculada
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        #vinculamos el socket con IP y puerto
        if tcp_socket.bind((args.host, args.port)) == -1:
            print("Error al vincular el socket con la IP y el puerto")
            sys.exit(-1)

        #escuchamos conexiones entrantes
        tcp_socket.listen(5) #recibe la conexión del cliente Máximo 5

        #bucle infinito para mantener el servidor activo indefinidamente
        while True:
            #aceptamos la conexión
            (client_socket, address) = tcp_socket.accept()

            #creamos un proceso hijo
            pid = os.fork()
            if pid == 0:

                #si es el proceso hijo se cierra el socket del padre 
                cerrar_conexion(tcp_socket)

                #procesamos las peticiones 
                process_web_request(client_socket, args.webroot)

                #salimos del proceso hijo
                sys.exit(0)
                
            else:
                #si es el proceso padre cerramos el socket que gestiona el hijo
                cerrar_conexion(client_socket)

    except KeyboardInterrupt:
        True

if __name__== "__main__":
    main()