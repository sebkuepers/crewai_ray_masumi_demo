#!/usr/bin/env python
import os
import uuid
import time
import asyncio
import logging
from random import randint

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import ray
from ray import serve

# Import your PoemFlow components
from crewai.flow import Flow, listen, start

# Set up a logger that aligns with Ray's logging format.
logger = logging.getLogger("serve")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(levelname)s %(asctime)s %(name)s %(process)d -- %(message)s'
)
handler.setFormatter(formatter)
# Ensure we don't add multiple handlers if this code runs repeatedly.
if not logger.handlers:
    logger.addHandler(handler)


# ---------------------------
# Load environment variables
# ---------------------------
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RAY_TOKEN = os.environ.get("RAY_TOKEN")
AGENT_IDENTIFIER = os.environ.get("AGENT_IDENTIFIER")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL")
PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY")

if not OPENAI_API_KEY:
    raise EnvironmentError("Please set the OPENAI_API_KEY environment variable.")


# ---------------------------
# PoemFlow Definition
# ---------------------------
class PoemState(BaseModel):
    sentence_count: int = 1
    num_poems: int = 5
    poems: list = []

class PoemFlow(Flow[PoemState]):
    @start()
    def generate_sentence_count(self):
        print("Generating sentence count")
        self.state.sentence_count = randint(1, 9)

    @listen(generate_sentence_count)
    def generate_poem(self):

        # Lazy import to avoid Pickling issues.
        from poem.crews.poem_crew.poem_crew import PoemCrew

        print("Generating poem(s)")
        if self.state.num_poems <= 1:
            result = PoemCrew().crew().kickoff(inputs={"sentence_count": self.state.sentence_count})
            print("Poem generated", result.raw)
            self.state.poems = [result.raw]
        else:
            # Generate multiple poems concurrently.
            tasks = [generate_single_poem.remote(self.state.sentence_count)
                     for _ in range(self.state.num_poems)]
            results = ray.get(tasks)
            print("Poems generated", results)
            self.state.poems = results

    @listen(generate_poem)
    def finalize_poem(self):
        print("Finalizing poem")
        # Additional processing if needed.

@ray.remote
def generate_single_poem(sentence_count: int):
    result = PoemCrew().crew().kickoff(inputs={"sentence_count": sentence_count})
    return result.raw

def kickoff(num_poems: int = 1):

    poem_flow = PoemFlow()
    poem_flow.state.num_poems = num_poems
    poem_flow.kickoff()
    return {
        "poems": poem_flow.state.poems,
        "sentence_count": poem_flow.state.sentence_count,
    }

# ---------------------------
# Pydantic Model for Request
# ---------------------------
class StartJobRequest(BaseModel):
    text: str = None       # for endpoint compatibility (not used in poem generation)
    num_poems: int = 1

# ---------------------------
# Payment-Poem Job Actor
# ---------------------------
@ray.remote
class PaymentPoemJobActor:
    def __init__(self, num_poems: int, agent_identifier: str):
        self.num_poems = num_poems
        self.agent_identifier = AGENT_IDENTIFIER
        self.status = "initialized"
        self.payment_status = "pending"
        self.result = None
        self.payment_id = None
        self.payment = None

    async def run(self):
        # Create a Payment instance and a payment request

        # Lazy import to avoid Pickling issues.
        from masumi_crewai.config import Config
        from masumi_crewai.payment import Payment, Amount

        # Initialize Masumi Payment Config
        payment_config = Config(
            payment_service_url=PAYMENT_SERVICE_URL,
            payment_api_key=PAYMENT_API_KEY
)
        self.payment = Payment(
            agent_identifier=self.agent_identifier,
            amounts=[Amount(amount="10000000", unit="lovelace")],
            config=payment_config
        )
        payment_request = await self.payment.create_payment_request()
        self.payment_id = payment_request["data"]["blockchainIdentifier"]
        self.status = "awaiting_payment"
        print(f"Job initialized. Payment ID: {self.payment_id}")
        # Start asynchronous payment monitoring.
        asyncio.create_task(self._monitor_payment())
        return {"payment_id": self.payment_id, "status": self.status}

    async def _monitor_payment(self):
        # Poll the payment status until it is marked as completed.
        while True:
            status_resp = await self.payment.check_payment_status()
            self.payment_status = status_resp.get("data", {}).get("status", "pending")
            print(f"Monitoring payment {self.payment_id}, status: {self.payment_status}")
            if self.payment_status == "completed":
                break
            await asyncio.sleep(2)  # Poll every 2 seconds

        # Payment confirmed; trigger poem generation.
        self.result = kickoff(self.num_poems)
        self.status = "completed"
        # Complete the payment on Masumi (using first poem’s snippet as reference).
        first_poem = self.result["poems"][0] if self.result["poems"] else ""
        await self.payment.complete_payment(self.payment_id, first_poem[:64])
        print(f"Payment {self.payment_id} completed and poem job executed.")

    async def get_status(self):
        return {
            "status": self.status,
            "payment_status": self.payment_status,
            "result": self.result,
            "payment_id": self.payment_id
        }

# ---------------------------
# Job Manager Actor
# ---------------------------
@ray.remote
class JobManager:
    def __init__(self, agent_identifier: str, jobs=None):
        self.agent_identifier = agent_identifier
        # If a jobs dictionary is provided, use it; otherwise, start fresh.
        self.jobs = jobs if jobs is not None else {}

    async def create_job(self, num_poems: int):
        job_id = str(uuid.uuid4())
        job_actor = PaymentPoemJobActor.remote(num_poems, self.agent_identifier)
        self.jobs[job_id] = job_actor
        # Start the job asynchronously.
        await job_actor.run.remote()
        return job_id

    async def get_status(self, job_id: str):
        job_actor = self.jobs.get(job_id)
        if not job_actor:
            return {"error": f"No job found with id {job_id}"}
        status = await job_actor.get_status.remote()
        return {"job_id": job_id, **status}

    def export_state(self):
        """Exports the current jobs dictionary for handover."""
        return self.jobs

# ---------------------------
# FastAPI Endpoints
# ---------------------------
app = FastAPI()

@app.post("/start_job")
async def start_job(request: StartJobRequest):
    """
    Initiates a poem generation job with Masumi payment integration.
    Accepts:
      - text: (optional, for compatibility)
      - num_poems: number of poems to generate.
    Returns the job ID, payment ID, and initial status.
    """
    # Retrieve the JobManager actor.
    manager = ray.get_actor("JobManager", namespace="serve")
    job_id = await manager.create_job.remote(request.num_poems)
    status = await manager.get_status.remote(job_id)
    return status

@app.get("/status")
async def job_status(job_id: str = None):
    if not job_id:
        raise HTTPException(status_code=400, detail="Please provide a job_id query parameter.")
    manager = ray.get_actor("JobManager", namespace="serve")
    status = await manager.get_status.remote(job_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status

@app.get("/availability")
async def availability():
    return {"status": "available", "message": "The server is running smoothly."}

# ---------------------------
# Ray Serve Deployment
# ---------------------------
@serve.deployment
@serve.ingress(app)
class MyFastAPIDeployment:
    pass

def main():
    # Shutdown any existing Ray instance.
    if ray.is_initialized():
        ray.shutdown()

    # Initialize Ray with environment variables.
    ray.init(
        address="auto",
        _redis_password=RAY_TOKEN,
        runtime_env={"env_vars": {
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "PAYMENT_SERVICE_URL": PAYMENT_SERVICE_URL,
            "PAYMENT_API_KEY": PAYMENT_API_KEY
        }}
    )

    serve.start()


    # Attempt to retrieve the existing JobManager actor and export its state.
    try:
        old_job_manager = ray.get_actor("JobManager", namespace="serve")
        try:
            state = ray.get(old_job_manager.export_state.remote())
        except AttributeError:
            # If the method isn't available, we can't migrate state.
            state = None
        # Kill the old actor after exporting its state.
        ray.kill(old_job_manager)
    except ValueError:
        # No existing actor found; initialize state as None.
        state = None

    # If state was handed over, log details.
    if state is not None:
        total_jobs = len(state)
        try:
            # Retrieve status from each PaymentPoemJobActor.
            statuses = ray.get([job_actor.get_status.remote() for job_actor in state.values()])
            # Count jobs that are not yet completed.
            running_count = sum(1 for s in statuses if s.get("status") != "completed")
        except Exception as e:
            logger.warning("Error querying job statuses during handover: %s", e)
            running_count = 0

        logger.info(
            "JobManagerActorHandover detected: %d jobs found in state; %d PaymentPoemJobActor(s) are still running.",
            total_jobs, running_count
        )
    else:
        logger.info("No existing JobManagerActor state to hand over.")

    # Create a new named, detached JobManager actor with the exported state (if any).
    JobManager.options(
        name="JobManager",
        namespace="serve",
        lifetime="detached"
    ).remote(AGENT_IDENTIFIER, jobs=state)

    # Deploy the FastAPI app.
    serve.run(MyFastAPIDeployment.bind(), route_prefix="/")

    # Keep the process alive.
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()