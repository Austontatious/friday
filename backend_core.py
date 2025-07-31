import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from friday.routes.friday import router as friday_router
from friday.persona_loader import persona
from friday.model_config import ModelType
from friday.tools.tool_controller import process_output

# ── Load the model ───────────────────────────────────────────────────
try:
    print("🔄 Attempting to load Friday model...")
    persona.load_model(ModelType.FRIDAY)
    print("✅ Friday model loaded and cached.")
except Exception as e:
    print(f"❌ Failed to load Friday model: {e}")

# ── Logging setup ────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("friday")

# ── FastAPI app setup ────────────────────────────────────────────────
app = FastAPI(title="FRIDAY AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Friday’s API router ────────────────────────────────────────
app.include_router(friday_router)

# ── Health Endpoints ────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/healthz")
async def health_probe():
    return {"status": "ok"}

@app.get("/friday/port")
async def port_discovery():
    return {"port": int(os.environ.get("PORT", 8000))}

@app.get("/")
async def root():
    return {"status": "FRIDAY backend alive"}

# ── Input Schema ─────────────────────────────────────────────────────
class InputModel(BaseModel):
    prompt: str

# ── Call model and return full output ───────────────────────────────
import re
import random

async def call_model(prompt: str) -> dict:
    MAX_AUTO_CONTINUES = 4  # Slightly more generous for realism
    STOP_TOKENS = ["<|im_end|>", "<|EOT|>", "THE END.", "[end]", "[finished]"]
    CONTINUATION_PHRASES = [
        "continue",
        "keep going",
        "don’t stop now",
        "go on...",
        "finish what you started",
        "you were saying?",
        "please continue where you left off",
        "keep talking",
        "…",
    ]
    # Regex: ends with incomplete sentence, ellipsis, dash, or mid-word
    abrupt_end_re = re.compile(r"(\.\.\.|—|–|-|[,;:]$| [A-Za-z]+$)")

    try:
        responses = []
        result = persona.generate_response(prompt)
        if not isinstance(result, dict):
            logger.warning(f"⚠️ Unexpected model output: {result}")
            return {"raw": str(result), "cleaned": str(result)}

        logger.info(f"✅ Cleaned response: {result.get('cleaned', '[no cleaned]')}")
        responses.append(result.get("cleaned", ""))

        auto_continues = 0
        while auto_continues < MAX_AUTO_CONTINUES:
            last = responses[-1].strip()
            done = False

            # 1. Check for known stop tokens or closing words
            for token in STOP_TOKENS:
                if last.lower().endswith(token.lower()):
                    done = True
                    break

            # 2. If ended with a real sentence and not abruptly, also stop
            if not done and last[-1:] in ".!?" and len(last) > 32:
                # If the last sentence is >32 chars and ends with terminal punctuation
                if not abrupt_end_re.search(last[-16:]):
                    done = True

            # 3. Detect abrupt/awkward endings (e.g. ellipsis, hanging word, open quote)
            if not done and (
                abrupt_end_re.search(last)
                or last.endswith("..")
                or last.endswith("…")
                or last.endswith('"') and last.count('"') % 2 != 0
            ):
                logger.info("🔄 Detected possible abrupt stop. Continuing...")
                pass  # Not done

            if done or not last:
                break

            # Pick a random, natural continuation phrase
            cont_phrase = random.choice(CONTINUATION_PHRASES)
            next_result = persona.generate_response(cont_phrase)
            if not isinstance(next_result, dict):
                logger.warning(f"⚠️ Unexpected continuation output: {next_result}")
                break
            next_cleaned = next_result.get("cleaned", "")
            responses.append(next_cleaned)
            auto_continues += 1

            # If new chunk ends with stop, break immediately
            for token in STOP_TOKENS:
                if next_cleaned.lower().strip().endswith(token.lower()):
                    break

        # Stitch everything together
        full_reply = "\n".join(responses).strip()
        result["cleaned"] = full_reply

        return result  # Includes raw, cleaned, affect (from first block only)
    except Exception as e:
        logger.error(f"🔥 Error in call_model: {e}")
        return {"raw": "[Error generating response]", "cleaned": "[Error generating response]", "affect": "error"}
# ── Primary Processing Endpoint ──────────────────────────────────────
@app.post("/process")
async def process(input: InputModel):
    output = await call_model(input.prompt)
    return output  # ← flattened, full structure returned directly


# ── Entrypoint ───────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"🚀 Serving FRIDAY at http://localhost:{port}")
    uvicorn.run("friday.backend_core:app", host="0.0.0.0", port=port, reload=False)

