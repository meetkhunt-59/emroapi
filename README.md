TODO LIST :

PREPROCESS :
    -remove bg in high edgh and inner design not detacting
    -path for desigh is not desiginig for complex design 




COMAND : uvicorn app.main:app --reload

DOCKER : docker build -t emroapi .
         docker run -p 8000:8000 emroapi

CLEAR DOCKER CONTAINERS :
         docker system prune -a -f

new things