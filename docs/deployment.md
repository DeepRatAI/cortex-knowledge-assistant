# Despliegue

Guía completa para desplegar Cortex Knowledge Assistant en diferentes entornos: desarrollo local, Docker, Kubernetes y producción.

---

## Resumen de Opciones

| Entorno                                                 | Método         | Complejidad | Uso Recomendado       |
| ------------------------------------------------------- | -------------- | ----------- | --------------------- |
| [Desarrollo Local](#desarrollo-local)                   | Python directo | Baja        | Desarrollo, debugging |
| [Docker Compose](#docker-compose)                       | Un comando     | Baja        | Demo, staging         |
| [Docker Compose Producción](#docker-compose-producción) | Compose + TLS  | Media       | Producción pequeña    |
| [Kubernetes](#kubernetes)                               | Manifests/Helm | Alta        | Producción escalable  |

---

## Desarrollo Local

Para desarrollo y debugging sin Docker.

### Requisitos

- Python 3.11+
- PostgreSQL 15+ (o SQLite para desarrollo rápido)
- Redis (opcional)
- Qdrant (opcional, usa StubRetriever sin él)

### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/DeepRatAI/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -e ".[dev]"

# 4. Configurar variables
export DATABASE_URL=sqlite:///./cortex.db
export CKA_LLM_PROVIDER=Fake
export JWT_SECRET_KEY=dev-secret-key-for-testing-only

# 5. Iniciar API
uvicorn src.cortex_ka.api.main:app --reload --host 0.0.0.0 --port 8088
```

### Iniciar UI (Desarrollo)

```bash
cd ui
npm install
npm run dev
```

Acceder a http://localhost:5173 (Vite dev server)

---

## Docker Compose

Método recomendado para la mayoría de los casos.

### Requisitos

- Docker 24.0+
- Docker Compose 2.20+
- 4GB RAM mínimo

### Despliegue Rápido

```bash
# 1. Clonar y configurar
git clone https://github.com/DeepRatAI/cortex-knowledge-assistant.git
cd cortex-knowledge-assistant
cp .env.example .env

# 2. Editar .env con tu configuración
nano .env

# 3. Iniciar
docker compose up -d

# 4. Verificar
docker compose ps
curl http://localhost:8088/health
```

### Estructura de Servicios

```yaml
services:
  cortex-api: # FastAPI backend
  cortex-ui: # React frontend (Nginx)
  postgres: # PostgreSQL 16
  qdrant: # Qdrant vector DB
  redis: # Redis cache
```

### Comandos Útiles

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Ver logs de un servicio específico
docker compose logs -f cortex-api

# Reiniciar un servicio
docker compose restart cortex-api

# Reconstruir después de cambios
docker compose build --no-cache
docker compose up -d

# Detener todo
docker compose down

# Detener y eliminar volúmenes (CUIDADO: borra datos)
docker compose down -v
```

### Volúmenes de Datos

```yaml
volumes:
  cortex_data: # /app/data - documentos, uploads
  postgres_data: # PostgreSQL data
  qdrant_data: # Qdrant vectors
  redis_data: # Redis persistence (opcional)
```

---

## Docker Compose Producción

Configuración hardened para producción.

### Cambios Respecto a Desarrollo

1. **TLS/HTTPS**: Reverse proxy con certificados
2. **Secrets**: Variables sensibles en Docker secrets
3. **Logging**: Centralizado con límites de rotación
4. **Health checks**: Configurados para todos los servicios
5. **Resource limits**: CPU y memoria limitados
6. **Network isolation**: Red interna sin exposición

### Archivo docker-compose.prod.yml

```yaml
version: "3.8"

services:
  nginx:
    image: nginx:alpine
    ports:
     - "443:443"
     - "80:80"
    volumes:
     - ./nginx.conf:/etc/nginx/nginx.conf:ro
     - ./certs:/etc/nginx/certs:ro
    depends_on:
     - cortex-api
     - cortex-ui
    networks:
     - frontend
    restart: unless-stopped

  cortex-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    env_file:
     - .env.prod
    secrets:
     - jwt_secret
     - hf_api_key
     - postgres_password
    environment:
     - JWT_SECRET_KEY_FILE=/run/secrets/jwt_secret
     - HF_API_KEY_FILE=/run/secrets/hf_api_key
    expose:
     - "8088"
    networks:
     - frontend
     - backend
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
        reservations:
          cpus: "0.5"
          memory: 1G
    restart: unless-stopped

  cortex-ui:
    build:
      context: ./ui
      dockerfile: Dockerfile
      args:
        VITE_DEMO_MODE: none
    expose:
     - "80"
    networks:
     - frontend
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    secrets:
     - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    volumes:
     - postgres_data:/var/lib/postgresql/data
    networks:
     - backend
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.12.1
    volumes:
     - qdrant_data:/qdrant/storage
    networks:
     - backend
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
     - redis_data:/data
    networks:
     - backend
    restart: unless-stopped

networks:
  frontend:
  backend:
    internal: true # No acceso externo

secrets:
  jwt_secret:
    file: ./secrets/jwt_secret.txt
  hf_api_key:
    file: ./secrets/hf_api_key.txt
  postgres_password:
    file: ./secrets/postgres_password.txt

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
```

### Configuración Nginx

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        server cortex-api:8088;
    }

    upstream ui {
        server cortex-ui:80;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;

        ssl_certificate /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

        # Security headers
        add_header Strict-Transport-Security "max-age=63072000" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;

        # API
        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health endpoints
        location ~ ^/(health|live|ready|metrics)$ {
            proxy_pass http://api;
        }

        # Auth endpoints
        location /auth/ {
            proxy_pass http://api/auth/;
        }

        # Query endpoints
        location /query {
            proxy_pass http://api/query;
            proxy_read_timeout 120s;
        }

        # SSE streaming
        location /query/stream {
            proxy_pass http://api/query/stream;
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
        }

        # UI (default)
        location / {
            proxy_pass http://ui;
        }
    }
}
```

### Despliegue Producción

```bash
# 1. Crear directorio de secrets
mkdir -p secrets
echo "$(openssl rand -base64 48)" > secrets/jwt_secret.txt
echo "hf_your_api_key" > secrets/hf_api_key.txt
echo "$(openssl rand -base64 24)" > secrets/postgres_password.txt
chmod 600 secrets/*

# 2. Obtener certificados (Let's Encrypt)
certbot certonly --standalone -d cortex.example.com
cp /etc/letsencrypt/live/cortex.example.com/*.pem certs/

# 3. Desplegar
docker compose -f docker-compose.prod.yml up -d
```

---

## Kubernetes

Despliegue escalable para producción enterprise.

### Requisitos

- Kubernetes 1.27+
- kubectl configurado
- Helm 3.x (opcional)
- Ingress Controller (nginx-ingress recomendado)
- Cert-Manager (para TLS automático)

### Estructura de Manifests

```
k8s/
├── api/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── hpa.yaml
├── ui/
│   ├── deployment.yaml
│   └── service.yaml
├── qdrant/
│   ├── statefulset.yaml
│   └── service.yaml
├── redis/
│   ├── deployment.yaml
│   └── service.yaml
├── networkpolicies/
│   └── cortex.yaml
├── ingress.yaml
├── configmap.yaml
└── secrets.yaml
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cortex-config
data:
  CKA_LLM_PROVIDER: "HF"
  CKA_USE_QDRANT: "true"
  CKA_USE_REDIS: "true"
  CKA_QDRANT_URL: "http://qdrant:6333"
  CKA_REDIS_HOST: "redis"
  CKA_HTTPS_ENABLED: "true"
  CKA_CORS_ORIGINS: "https://cortex.example.com"
  CKA_LOG_LEVEL: "INFO"
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: cortex-secrets
type: Opaque
stringData:
  JWT_SECRET_KEY: "your-production-secret-key"
  HF_API_KEY: "hf_xxxx"
  POSTGRES_PASSWORD: "secure-password"
  DATABASE_URL: "postgresql+psycopg://cortex:secure-password@postgres:5432/cortex"
```

### API Deployment

```yaml
# k8s/api/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cortex-api
  labels:
    app: cortex-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cortex-api
  template:
    metadata:
      labels:
        app: cortex-api
    spec:
      containers:
       - name: cortex-api
          image: ghcr.io/deepratai/cortex-api:0.1.0-beta
          ports:
           - containerPort: 8088
          envFrom:
           - configMapRef:
                name: cortex-config
           - secretRef:
                name: cortex-secrets
          resources:
            limits:
              cpu: "2"
              memory: 4Gi
            requests:
              cpu: "500m"
              memory: 1Gi
          livenessProbe:
            httpGet:
              path: /live
              port: 8088
            initialDelaySeconds: 15
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8088
            initialDelaySeconds: 10
            periodSeconds: 5
          volumeMounts:
           - name: data
              mountPath: /app/data
      volumes:
       - name: data
          persistentVolumeClaim:
            claimName: cortex-data
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cortex-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: 50m
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
spec:
  tls:
   - hosts:
       - cortex.example.com
      secretName: cortex-tls
  rules:
   - host: cortex.example.com
      http:
        paths:
         - path: /api
            pathType: Prefix
            backend:
              service:
                name: cortex-api
                port:
                  number: 8088
         - path: /auth
            pathType: Prefix
            backend:
              service:
                name: cortex-api
                port:
                  number: 8088
         - path: /query
            pathType: Prefix
            backend:
              service:
                name: cortex-api
                port:
                  number: 8088
         - path: /health
            pathType: Exact
            backend:
              service:
                name: cortex-api
                port:
                  number: 8088
         - path: /
            pathType: Prefix
            backend:
              service:
                name: cortex-ui
                port:
                  number: 80
```

### Horizontal Pod Autoscaler

```yaml
# k8s/api/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cortex-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cortex-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
   - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
   - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Desplegar en Kubernetes

```bash
# 1. Crear namespace
kubectl create namespace cortex

# 2. Aplicar secrets y configmap
kubectl apply -f k8s/secrets.yaml -n cortex
kubectl apply -f k8s/configmap.yaml -n cortex

# 3. Desplegar base de datos (usar operadores en producción real)
kubectl apply -f k8s/redis/ -n cortex
kubectl apply -f k8s/qdrant/ -n cortex
# PostgreSQL: usar operador como CloudNativePG

# 4. Desplegar aplicación
kubectl apply -f k8s/api/ -n cortex
kubectl apply -f k8s/ui/ -n cortex

# 5. Configurar ingress
kubectl apply -f k8s/ingress.yaml -n cortex

# 6. Verificar
kubectl get pods -n cortex
kubectl get ingress -n cortex
```

---

## Monitoreo en Producción

### Prometheus + Grafana

```yaml
# k8s/servicemonitor.yaml (requiere Prometheus Operator)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: cortex-api
spec:
  selector:
    matchLabels:
      app: cortex-api
  endpoints:
   - port: http
      path: /metrics
      interval: 30s
```

### Métricas Clave a Monitorear

| Métrica                                          | Alerta Sugerida   |
| ------------------------------------------------ | ----------------- |
| `cortex_query_latency_seconds{quantile="0.95"}`  | > 5s              |
| `cortex_http_requests_total{status_class="5xx"}` | Incremento súbito |
| `cortex_http_requests_total{status_class="4xx"}` | > 10% del total   |
| Container CPU utilization                        | > 80%             |
| Container Memory                                 | > 85%             |

### Logging Centralizado

```yaml
# Fluentd/Fluentbit para enviar logs a Elasticsearch/Loki
annotations:
  fluentbit.io/parser: json
```

---

## CI/CD

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    tags:
     - "v*"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
     - uses: actions/checkout@v4

     - name: Build and push API
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.api
          push: true
          tags: ghcr.io/${{ github.repository }}/api:${{ github.ref_name }}

     - name: Build and push UI
        uses: docker/build-push-action@v5
        with:
          context: ./ui
          push: true
          tags: ghcr.io/${{ github.repository }}/ui:${{ github.ref_name }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
     - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/cortex-api \
            cortex-api=ghcr.io/${{ github.repository }}/api:${{ github.ref_name }}
          kubectl set image deployment/cortex-ui \
            cortex-ui=ghcr.io/${{ github.repository }}/ui:${{ github.ref_name }}
```

---

## - Checklist de Despliegue

### Pre-Despliegue

- [ ] Configurar todos los secrets
- [ ] Verificar certificados TLS
- [ ] Configurar DNS
- [ ] Revisar límites de recursos
- [ ] Configurar backups automáticos

### Post-Despliegue

- [ ] Verificar `/health` retorna `healthy`
- [ ] Verificar `/ready` retorna `200`
- [ ] Crear usuario admin inicial
- [ ] Ingestar documentos de prueba
- [ ] Probar query de ejemplo
- [ ] Verificar logs en sistema de monitoreo
- [ ] Configurar alertas

### Mantenimiento

- [ ] Rotación de logs configurada
- [ ] Backups probados y verificados
- [ ] Plan de disaster recovery documentado
- [ ] Runbook de operaciones creado

---

<p align="center">
  <a href="security.md">← Seguridad</a> •
  <a href="development.md">Desarrollo →</a>
</p>
