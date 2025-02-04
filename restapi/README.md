## Running the server

In the server side, run the following:

```console
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## Client side getting information

```console
curl -X GET "http://192.168.82.25:8000/models"

{"models":["NAME                      MODIFIED      SIZE     ","ollama://tinyllama:latest 3 minutes ago 608.16 MB"]}% 
```

## Posting data

```console
curl -X POST "http://192.168.82.25:8000/run/tinyllama" &
```
