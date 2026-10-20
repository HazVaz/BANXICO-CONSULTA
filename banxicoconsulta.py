import os
import sys
import time
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env local
load_dotenv()

# Variables de configuración extraídas del .env
BANXICO_TOKEN = os.getenv("BANXICO_TOKEN")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def preguntar_siguiente_accion() -> None:
    """
    Pregunta al usuario si desea regresar al menú principal o salir del programa.
    """
    print("\n------------------------------------------")
    print("¿Qué desea hacer a continuación?")
    print("1. Regresar al menú principal")
    print("2. Salir del programa")
    print("------------------------------------------")
    
    opcion = input("Seleccione una opción (1 o 2): ").strip()
    if opcion == "2":
        salir_programa()

def salir_programa() -> None:
    """
    Finaliza la ejecución del programa con un retraso de 5 segundos.
    """
    print("\nCerrando programa...")
    time.sleep(1)
    print("3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("¡Programa finalizado!")
    sys.exit()

def consultar_banxico_serie() -> None:
    """
    Solicita dinámicamente cualquier clave de serie al usuario
    y realiza la consulta HTTP en tiempo real a Banxico.
    """
    if not BANXICO_TOKEN:
        print("\nError: No se encontró BANXICO_TOKEN en el archivo .env")
        preguntar_siguiente_accion()
        return

    serie = input("\nIngrese la clave de la serie de Banxico (ej. SF43718, SF61745, SP68257): ").strip()

    if not serie:
        print("Error: Debe ingresar una clave de serie válida.")
        preguntar_siguiente_accion()
        return

    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie}/datos/oportuno"
    headers = {"Bmx-Token": BANXICO_TOKEN}

    try:
        print(f"\n-Consultando la serie '{serie}' en Banxico...")
        response = requests.get(url, headers=headers, timeout=10)

        # Comprobación de conectividad HTTP
        if response.status_code == 200:
            datos = response.json()
            print("\n-Conexión exitosa a Banxico.")

            series_list = datos.get("bmx", {}).get("series", [])
            if series_list:
                info_serie = series_list[0]
                titulo = info_serie.get("titulo", "Sin título")
                observaciones = info_serie.get("datos", [])

                print(f"Serie  : {serie}")
                print(f"Título : {titulo}")
                if observaciones:
                    print(f"Fecha  : {observaciones[0].get('fecha')}")
                    print(f"Dato   : {observaciones[0].get('dato')}")
                else:
                    print("No se encontraron observaciones para esta serie.")
            else:
                print("Respuesta:", datos)
        else:
            print(f"\nError de conectividad/serie no encontrada. Código HTTP: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"\nError al conectar con el servidor de Banxico: {e}")

    preguntar_siguiente_accion()


def enviar_correo(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """
    Envía un correo electrónico utilizando la configuración SMTP (.env).
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("\n[-] Error: Faltan credenciales SMTP_USER o SMTP_PASSWORD en el .env")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        print("\n[+] Conectando al servidor SMTP...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)

        server.send_message(msg)
        server.quit()
        print("¡Correo enviado con éxito!")
        return True

    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return False


def calcular_isc() -> None:
    """
    Consulta automáticamente la tasa actual semanal de CETES (Serie SF43936) en Banxico,
    pide al usuario el monto y las semanas de inversión, calcula el interés,
    genera un reporte y lo envía por correo.
    """
    if not BANXICO_TOKEN:
        print("\n[-] Error: No se encontró BANXICO_TOKEN en el archivo .env")
        preguntar_siguiente_accion()
        return

    # 1. Consulta automática de la tasa actual de CETES a 28 días (Serie semanal SF43936)
    serie_cetes = "SF43936"
    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie_cetes}/datos/oportuno"
    headers = {"Bmx-Token": BANXICO_TOKEN}

    tasa_anual = 0.0625  # Tasa de respaldo por defecto en caso de fallo de red
    try:
        print(f"\nConsultando la tasa actual semanal de CETES en Banxico...")
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            datos = response.json()
            series_list = datos.get("bmx", {}).get("series", [])
            if series_list:
                observaciones = series_list[0].get("datos", [])
                if observaciones:
                    tasa_str = observaciones[0].get("dato")
                    tasa_anual = float(tasa_str) / 100
                    print(f"Tasa CETES vigente obtenida ({observaciones[0].get('fecha')}): {tasa_str}% anual")
        else:
            print(f"No se pudo conectar con Banxico (Código {response.status_code}). Usando tasa estándar de 6.0%.")
    except Exception as e:
        print(f"Error al consultar la tasa de CETES: {e}. Usando tasa estándar de 6.0%.")

    # 2. Solicitar datos al usuario (Monto y Semanas)
    try:
        print("\n--- Cálculo de Interés con CETES SERIE SEMANAl ---")
        monto = float(input("Ingrese el monto que va a invertir ($): "))
        semanas = int(input("Ingrese las semanas que va a mantener la inversión: "))

        if monto <= 0 or semanas <= 0:
            print("[-] Error: El monto y las semanas deben ser mayores a cero.")
            preguntar_siguiente_accion()
            return

        # 3. Resolución de la fórmula (Convertir semanas a días usando base comercial de 360 días)
        dias = semanas * 7
        interes = monto * tasa_anual * (dias / 360)
        monto_total = monto + interes

        reporte = (
            f"====== REPORTE ISC (CETES) ======\n"
            f"Tasa CETES Aplicada (Banxico) : {tasa_anual * 100:.2f}%\n"
            f"Monto Invertido               : ${monto:,.2f}\n"
            f"Plazo                         : {semanas} semana(s) ({dias} días)\n"
            f"Interés Ganado                : ${interes:,.2f}\n"
            f"Total al Final                : ${monto_total:,.2f}\n"
            f"================================="
        )
        # print(f"\n{reporte}")

        correo_destino = input("\nIngrese el correo al que desea enviar el reporte: ").strip()

        print("\n[+] Procesando reporte...")
        time.sleep(1)  # Delay de procesamiento

        if correo_destino:
            enviar_correo(
                destinatario=correo_destino,
                asunto="Reporte de Cálculo de Interés CETES POR EL ASESOR: ANGEL HAZIEL",
                cuerpo=reporte
            )

    except ValueError:
        print("\n[-] Error: Ingrese únicamente números válidos.")
    except Exception as e:
        print(f"[-] Error en el cálculo: {e}")

    # Pausa interactiva antes de volver al menú
    preguntar_siguiente_accion()





def mostrar_menu() -> None:
    """
    Despliega el menú principal e interactúa iterativamente con el usuario.
    """
    while True:
        print("\n==========================================")
        print("             MENÚ PRINCIPAL               ")
        print("==========================================")
        print("¿ Consultar serie de Banxico ?")
        print("Teclea 1")
        print("Calcular Interés con CETES ?")
        print("Teclea 2")
        print("Salir del programa salir")
        print("Teclear 3")
        print("==========================================")

        try:
            opcion = input("Seleccione una opción: ").strip()

            if opcion == "1":
                consultar_banxico_serie()
            elif opcion == "2":
                calcular_isc()
            elif opcion == "3":
                salir_programa()
            else:
                print("\n Opción no válida. Por favor teclee 1, 2 o 3.")

        except KeyboardInterrupt:
            print("\n Interrupción del sistema detectada.")
            salir_programa()
        except Exception as e:
            print(f"\n Error inesperado: {e}")


if __name__ == "__main__":
    mostrar_menu()