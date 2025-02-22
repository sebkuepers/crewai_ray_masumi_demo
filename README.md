# CrewAI Ray Masumi Demo

This is a simple demo to showcase how you can run a CrewAI Flow (the standard poem flow) on a locally hosted Ray Cluster and deploy it with Ray Serve, while we have this Agentic Services actually registered on the Masumi Network Preprod environment for it to accept payments for execution.

We are using hatch to handle the dependencies and the packaging.

```bash
pip install hatch
```

!!! warning
    You will need to have your own Masumi Payment Service up and running to test this demo.

### Related Documentation:
- [Masumi Documentation](https://docs.masumi.network/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [Ray Documentation](https://docs.ray.io/)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sebkuepers/CrewAI_Ray_Masumi_Demo.git
cd CrewAI_Ray_Masumi_Demo
```

### 2. Configure the environment variables

```env
OPENAI_API_KEY=your_openai_api_key
RAY_TOKEN=your_ray_token
AGENT_IDENTIFIER=your_agent_identifier
PAYMENT_SERVICE_URL=your_payment_service_url
PAYMENT_API_KEY=your_payment_api_key
```

- RAY_TOKEN you can set yourself.
- PAYMENT_SERVICE_URL is the URL of the Masumi Payment Service.
- PAYMENT_API_KEY is the API Key of the Masumi Payment Service.

AGENT_IDENTIFIER is the identifier you get after registering your Agentic Service on the Masumi Network. We provide you an easy way to register this demo. See below.

### 3. Install the project in editable mode
With hatch installed, run:

```bash
pip install -e .
```
This will set up your environment so that any changes to the code are immediately reflected.

## Register the Demo

To register the demo, you first edit the registration.yaml file to change the name, description, author, etc. of the demo:

```yaml
example_output: "example_output"
tags:
  - "tag1"
  - "tag2"
name: "CrewAI Ray Masumi Demo"
api_url: "http://localhost:8000"
description: "A Demo to showcase CrewAI, Ray, and Masumi"
author:
  name: "Your Name"
  contact: "author@example.com"
  organization: "Author Organization"
legal:
  privacy_policy: "https://example.com/privacy"
  terms: "https://example.com/terms"
  other: "https://example.com/legal"
capability:
  name: "Capability Name"
  version: "1.0.0"
requests_per_hour: "100"
pricing:
  - unit: "usdm"
    quantity: "10000000"
```

Then you run the register script:

```bash
hatch run register
```

This will register the demo on the Masumi Network Preprod environment and set the AGENT_IDENTIFIER environment variable automatically in your .env file.

## Running the Demo

If you want to run the CrewAI flow once as a test without Ray or Masumi involved, you can do so with the following command:

```bash
hatch run kickoff
```
Be aware that this will only work with the default "num_poems" value of 1.
With multiple poems, the flow will not work, as it would expect the Ray Cluster to distribute the work of writing the poems into concurrent tasks.

So let's start the Ray Cluster locally with the RAY_TOKEN you set in the environment variables.

```bash
ray start --head --redis-password <RAY_TOKEN>
```

Then you serve the FastAPI app to the Ray Cluster, by running the hatch script:

```bash
hatch run serve
```

To start the CrewAI flow and pay for it, you can run the following command in a separate terminal form the same directory:

```bash
hatch run start_and_pay
```

This will start the CrewAI flow and pay for it, using the Masumi Payment Service.

To check the status of the job, you can run the following command:

```bash
curl http://localhost:8000/status?job_id=<job_id>
```



