# CrewAI Ray Masumi Demo

Thi is a simple demo to showcase how you can run a CrewAI Flow (the standard poem flow) on a locally hosted Ray Cluster and deploy it with Ray Serve, while we have this Agentic Services actually registered on the Masumi Network Preprod environment and implemented the Agentic Service API endpoints, for it to accept payments for execution.

We are using hatch to handle the dependencies and the packaging.

```bash
pip install hatch
```

## Setup

1. Clone the repository

```bash
git clone https://github.com/sebkuepers/CrewAI_Ray_Masumi_Demo.git
cd CrewAI_Ray_Masumi_Demo
```

2. Configure the environment variables

```env
OPENAI_API_KEY=your_openai_api_key
RAY_TOKEN=your_ray_token
PAYMENT_SERVICE_URL=your_payment_service_url
PAYMENT_API_KEY=your_payment_api_key
```

RAY_TOKEN you can set yourself.
PAYMENT_SERVICE_URL is the URL of the Masumi Payment Service.
PAYMENT_API_KEY is the API Key of the Masumi Payment Service.

3. Install the project in editable mode
With hatch installed, run:

```bash
pip install -e .
```
This will set up your environment so that any changes to the code are immediately reflected.

## Running the Demo

First you need to start the Ray Cluster.

```bash
ray start --head --redis-password <RAY_TOKEN>
```

Then you serve the FastAPI app to the Ray Cluster

```bash
hatch run serve
```

This will serve the FastAPI app to the Ray Cluster and you can now access the endpoints.

```bash
curl -X POST "http://localhost:8000/start_job" -H "Content-Type: application/json" -d '{"num_poems": 1}'
```





