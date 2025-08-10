# market-data-api

A stateless micro‑service delivering your dreams.


## 🐍 PyFast Kafka Template – FastAPI + Kafka + K8s

A stateless FastAPI microservice template with first-class Kafka support, production-grade health probes, and container lifecycle management via Haraka Runtime.

---

## 🚀 Features

- ✅ **FastAPI + Uvicorn**: Lightweight, blazing-fast async API.
- ✅ **Kafka Consumer**: Integrated via `aiokafka`, supports retries and async loops.
- ✅ **Readiness + Liveness Probes**: K8s-native `/health/live` and `/health/ready` endpoints.
- ✅ **Pluggable Startup Lifecycle**: Runtime hooks for clean init/shutdown.
- ✅ **Helm + Skaffold**: Easy to deploy locally or to any K8s cluster.
- ✅ **Extensible Template**: Powered by [Haraka](https://github.com/your-org/haraka), ready for plug-in expansion.

---

## 🧱 Stack

| Layer           | Tech                              |
|----------------|------------------------------------|
| API            | [FastAPI](https://fastapi.tiangolo.com)          |
| Kafka Client   | [aiokafka](https://aiokafka.readthedocs.io/en/stable/)       |
| Runtime        | [Haraka Runtime](https://github.com/your-org/haraka)         |
| Infra          | Helm, Skaffold, kind (or K8s)       |
| Dev Tools      | curl, kafka-console-producer/consumer |

---

## 🛠️ Local Development

### ▶️ Prerequisites

- Docker + Kubernetes (via [kind](https://kind.sigs.k8s.io/))
- [Skaffold](https://skaffold.dev/)
- Python 3.10+ (or 3.12)
- Optional: Kafka CLI tools (bundled in container)

### 🚢 Run Locally

```bash
  skaffold dev -p dev
```

This will:

1. Build and deploy your FastAPI app
2. Deploy a 3-node Kafka cluster via Bitnami Helm chart
3. Forward port `8000` for HTTP access

---

## 🔗 API Endpoints

| Endpoint          | Purpose              |
|-------------------|----------------------|
| `/pyman-3/docs`   | Swagger UI           |
| `/healthz`        | Combined liveness/readiness |
| `/health/live`    | Liveness probe       |
| `/health/ready`   | Kafka readiness      |

---

## 📬 Kafka

### Produce a Message

```bash
  kubectl exec -it <kafka-pod> -- \
  kafka-console-producer.sh --bootstrap-server pyman-3-kafka:9092 --topic example-topic
```

Enter:
```
Hello from CLI
```

### Consume Messages

```bash
  kubectl exec -it <kafka-pod> -- \
  kafka-console-consumer.sh --bootstrap-server pyman-3-kafka:9092 --topic example-topic --from-beginning
```

---

## 🧪 Health Probes

Liveness and readiness logic follows a staged pattern:

- Waits 15s for cluster to stabilize
- Retries Kafka bootstrap up to 10 times with exponential backoff
- Uses a shared `set_kafka_ready()` status for `/health/ready`

---

## 📂 Project Structure

```text
src/
├── app/
│   ├── core/            # Config, router, runtime
│   ├── services/        # Kafka consumers
│   ├── schemas/         # Pydantic models
│   ├── swagger_config/  # Custom OpenAPI setup
chart/                   # Helm chart
skaffold.yaml            # Skaffold config
```

---

## 🧩 Extending the Template

This project was generated using the [`haraka`](https://github.com/your-org/haraka) microservice scaffold engine. You can:

- Add Kafka producers with `aiokafka.AIOKafkaProducer`
- Swap Kafka for another broker (NATS, RabbitMQ)
- Add custom background workers or metrics

---

## 📄 License

MIT — © Your Name or Org



