import subprocess
import sys
import json


def run_command(command):
    """Ejecuta un comando del sistema y muestra la salida en tiempo real."""
    try:
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for line in process.stdout:
            sys.stdout.write(line.decode())
        for line in process.stderr:
            sys.stderr.write(line.decode())
        process.wait()
        if process.returncode != 0:
            raise Exception(f"Error ejecutando comando: {command}")
    except Exception as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(1)


def create_container(resource_group, container_name, acr_name, image_name, dns_label):
    print(f"Creando contenedor '{container_name}' desde la imagen '{acr_name}.azurecr.io/{image_name}'...")

    # Obtener credenciales del ACR
    username = subprocess.check_output(
        f"az acr credential show --name {acr_name} --query 'username' --output tsv", shell=True
    ).decode().strip()
    password = subprocess.check_output(
        f"az acr credential show --name {acr_name} --query 'passwords[0].value' --output tsv", shell=True
    ).decode().strip()

    # Crear el contenedor con `--os-type Linux`
    command = (
        f"az container create "
        f"--resource-group {resource_group} "
        f"--name {container_name} "
        f"--image {acr_name}.azurecr.io/{image_name} "
        f"--os-type Linux "  # Aquí se especifica el tipo de sistema operativo
        f"--registry-login-server {acr_name}.azurecr.io "
        f"--registry-username {username} "
        f"--registry-password {password} "
        f"--cpu 1 "
        f"--memory 1 "
        f"--dns-name-label {dns_label} "
        f"--ports 80"
    )
    run_command(command)

def get_container_status(resource_group, container_name):
    print(f"Obteniendo estado del contenedor '{container_name}'...")
    command = f"az container show --name {container_name} --resource-group {resource_group} --output json"
    output = subprocess.check_output(command, shell=True).decode()
    container_info = json.loads(output)
    state = container_info["instanceView"]["state"]
    fqdn = container_info["ipAddress"]["fqdn"]
    print(f"Estado del contenedor: {state}")
    print(f"URL pública: http://{fqdn}")
    return state, fqdn


def main():
    # Configuración
    resource_group = "TutorialesMLearn"
    acr_name = "testdeazurecontenedor"
    image_name = "grupo_jolly_web_scraping:latest"
    container_name = "grupo-jolly-container"
    dns_label = "grupo-jolly-container-dns"

    # Crear el contenedor
    create_container(resource_group, container_name, acr_name, image_name, dns_label)

    # Verificar el estado del contenedor
    state, fqdn = get_container_status(resource_group, container_name)
    if state == "Running":
        print(f"El contenedor está corriendo y es accesible en: http://{fqdn}")
    else:
        print("El contenedor no se está ejecutando. Revisa los logs para más detalles.")


if __name__ == "__main__":
    main()
