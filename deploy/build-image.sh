docker build -f deploy/Dockerfile-base -t thanhlcm90/xiaozhi-server-base:latest .
docker build -f deploy/Dockerfile-server -t thanhlcm90/xiaozhi-server:latest .
docker build -f deploy/Dockerfile-web -t thanhlcm90/xiaozhi-server-web:latest .