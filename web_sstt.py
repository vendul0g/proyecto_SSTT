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
TIMEOUT_CONNECTION = 20 # Timout para la conexión persistente
MAX_ACCESOS = 10

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
    # return cs.send(data.encode("utf-8"))
    #comprobamos el tamaño del mensaje 
    if len(data) > BUFSIZE:
        #dividimos el mensaje en trozos de 8192
        trozos = [data[i:i+BUFSIZE] for i in range(0, len(data), BUFSIZE)]

        #enviamos los trozos
        for trozo in trozos:
            cs.send(trozo.encode("utf-8"))


def crear_mensaje_error(code, msg):
    """ Esta función construye un mensaje de error HTTP
        Devuelve el mensaje de error
    """
    return ("\nHTTP/1.1 " + str(code) + " " + msg + "\n\n")

def crear_mensaje_ok(content_type, content_length, cookie_counter):
    """ Esta función construye un mensaje de respuesta HTTP
        Devuelve el mensaje de respuesta
    """
    return ("\n"
            + "HTTP/1.1 200 OK\n"
            + "Date: " + datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT") + "\n"
            + "Server: Python/3.6.3\n"
            + "Connection: close\n"
            + "Set-Cookie: cookie_counter=" + str(cookie_counter) + "\n"
            + "Content-Length: " + str(content_length) + "\n"
            + "Content-Type: " + content_type + "\n\n")


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


def process_cookies(headers,  cs):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    pass

def is_method_http(method):
    """ Esta función comprueba si el método está incluido
        en la lista de métodos admitidos por HTTP.
    """
    return method in ["GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"]

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
    --                * Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
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
    
    error = False
    #bucle para esperar hasta que lleguen datos en la red 
    while True:
        if error: #mandamos mensaje si hubo un error
            print("error") #TODO borrar
            error = False
            enviar_mensaje(cs, crear_mensaje_error(400, "Bad Request"))
        
        #Esperamos respuesta del cliente
        rsublist, wsublist, xsublist = select.select([cs], [], [], TIMEOUT_CONNECTION)

        #comprobamos timeout excedido
        if not rsublist:
            print("timeout excedido")
            #TODO si hay un error, enviar informe de error
            return
        rsublist = [] #limpiamos la lista

        #Si hay datos en rsublist y timeout no excedido
        data = recibir_mensaje(cs)
        if not data:
            print("no hay datos") #TODO borrar
            return

        #analizamos la linea de solicitud
        lines = data.split('\r\n')
        print("lines=",lines) #TODO borrar
        if len(lines) < 2:
            error = True
            continue

        headers = []#obtenemos la lista de cabeceras
        i=1
        while lines[i]:
            headers.append(lines[i])
            i=i+1
        print("headers=",headers) #TODO borrar

        #comprobamos que la linea de solicitud esta bien formateada
        req = lines[0].split(' ') # req = [method, url, vesion]
        if len(req) != 3: #bad request
            error = True
            continue
        
        if req[2] != "HTTP/1.1": #comprobar version
            enviar_mensaje(cs, crear_mensaje_error(505, "Version Not Supported")) 
            continue
        
        
        if not is_method_http(req[0]): #comprobar si es un metodo valido
            enviar_mensaje(cs, crear_mensaje_error(405, "Method Not Allowed"))
            continue

        #leemos la url y eliminamos parametros
        url = req[1].split('?')[0]

        #comprobamos si el recurso solicitado es /
        if url == "/":
            url = "index.html"
        elif url[0] == "/": #eliminamos la barra inicial
            url = url.split("/")[1]
        
        #construimos la ruta absoluta del recurso
        path = webroot + url
        print(path) #TODO borrar

        #compobamos que el recurso existe
        if not os.path.isfile(path):
            enviar_mensaje(cs, crear_mensaje_error(404, "Not Found"))
            continue

        #analizamos las cabeceras
        process_cookies(headers, cs) #TODO

        #obtener el tamaño del recurso en bytes
        size = os.path.getsize(path)

        #extraer la extension para obtener el tipo de archivo
        extension = url.split('.')[1]

        #preparamos la respuesta con codigo 200
        response = crear_mensaje_ok(extension, size, 0).encode('utf-8') #TODO cookie_counter

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

        print("Todo correcto")  




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
        tcp_socket.listen(1) #recibe la conexión del cliente

        #bucle infinito para mantener el servidor activo indefinidamente
        while True:
            #aceptamos la conexión
            (client_socket, address) = tcp_socket.accept()

            #creamos un proceso hijo
            pid = os.fork()
            if pid == 0:
                #si es el proceso hijo se cierra el socket del padre 
                tcp_socket.close()

                #procesamos las peticiones 
                process_web_request(client_socket, args.webroot)

                #cerramos el socket
                cerrar_conexion(client_socket)

                #salimos del proceso hijo
                sys.exit(0)
                
            else:
                #si es el proceso padre cerramos el socket que gestiona el hijo
                cerrar_conexion(client_socket)

    except KeyboardInterrupt:
        True

if __name__== "__main__":
    main()


#https://realpython.com/python-sockets/#tcp-sockets