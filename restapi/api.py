from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import subprocess

app = FastAPI()


# Redirect root "/" to "/docs"
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/info")
def info_command():
    try:
        result = subprocess.run(
                ["ramalama", "info"], capture_output=True, text=True
        )
        return {"info": result.stdout.strip().split("\n")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/ps")
def ps_command():
    try:
        result = subprocess.run(
                ["ramalama", "ps"], capture_output=True, text=True
        )
        return {"ps": result.stdout.strip().split("\n")}
    except Exception as e:
        return {"error": str(e)}


# List available AI models in RamaLama
@app.get("/models")
def list_models():
    try:
        result = subprocess.run(
                ["ramalama", "list"], capture_output=True, text=True
        )
        return {"models": result.stdout.strip().split("\n")}
    except Exception as e:
        return {"error": str(e)}


# Pull method
@app.post("/pull/{model_name}")
def pull_model(model_name: str):
    try:
        command = ["ramalama", "pull", model_name]
        subprocess.run(command, check=True)
        return {"message": f"Model {model_name} is running"}
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


# Run an AI model
# (chatbot will open in the server side at this moment)
@app.post("/run/{model_name}")
def run_model(model_name: str):
    try:
        command = ["ramalama", "run", model_name]
        subprocess.run(command, check=True)
        return {"message": f"Model {model_name} is running"}
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


# Stop a running AI model
@app.post("/stop/{model_name}")
def stop_model(model_name: str):
    try:
        subprocess.run(["ramalama", "stop", model_name], check=True)
        return {"message": f"Model {model_name} stopped"}
    except Exception as e:
        return {"error": str(e)}
