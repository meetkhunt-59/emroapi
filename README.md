TODO LIST :

PREPROCESS :
    -remove bg in high edgh and inner design not detacting
    -path for desigh is not desiginig for complex design 
    -improve image to svg conversation by any ways like using ml model etc.
    -upload is not giving job id as it generate it gives after the job is completed



COMAND : uvicorn app.main:app --reload

DOCKER : docker build -t emroapi .
         docker run -p 9000:9000 emroapi

CLEAR DOCKER CONTAINERS :
         docker system prune -a -f
         