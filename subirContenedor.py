import subprocess
import sys


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


def login_to_acr(acr_name):
    print(f"Autenticando en el registro de Azure: {acr_name}...")
    run_command(f"az acr login --name {acr_name}")


def tag_and_push_image(acr_name, local_image, remote_image):
    print(f"Etiquetando imagen local {local_image} como {acr_name}.azurecr.io/{remote_image}...")
    run_command(f"docker tag {local_image} {acr_name}.azurecr.io/{remote_image}")
    
    print(f"Subiendo imagen al registro {acr_name}...")
    run_command(f"docker push {acr_name}.azurecr.io/{remote_image}")


def create_container_instance(resource_group, container_name, acr_name, image_name, dns_label):
    print(f"Creando contenedor {container_name} desde la imagen {acr_name}.azurecr.io/{image_name}...")
    command = (
        f"az container create "
        f"--resource-group {resource_group} "
        f"--name {container_name} "
        f"--image {acr_name}.azurecr.io/{image_name} "
        f"--registry-login-server {acr_name}.azurecr.io "
        f"--registry-username $(az acr credential show --name {acr_name} --query 'username' --output tsv) "
        f"--registry-password $(az acr credential show --name {acr_name} --query 'passwords[0].value' --output tsv) "
        f"--dns-name-label {dns_label} "
        f"--cpu 1 "
        f"--memory 1 "
        f"--ports 80"
    )
    run_command(command)


def main():
    # Configuración
    resource_group = "TutorialesMLearn"
    acr_name = "GrupoJollyTest"
    local_image = "grupo_jolly_web_scraping:latest"
    remote_image = "grupo_jolly_web_scraping:latest"
    container_name = "grupo-jolly-container"
    dns_label = "grupo-jolly-container-dns"

    # Pasos
    login_to_acr(acr_name)
    tag_and_push_image(acr_name, local_image, remote_image)
    create_container_instance(resource_group, container_name, acr_name, remote_image, dns_label)
    print("¡Proceso completado con éxito!")


if __name__ == "__main__":
    main()
