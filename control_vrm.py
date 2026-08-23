"""
VRM Avatar Control Server
Drives a VRM model via VMC protocol (OSC/UDP) for blendshape-based animation.
Compatible with VPuppr, VSeeFace, and other VMC-capable receivers.
"""
import socket
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pythonosc import osc_message_builder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VRMControl")

app = FastAPI(title="VRM Control Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

VMC_IP = "127.0.0.1"
VMC_PORT = 39539

# Standard VRM 1.0 blendshapes
BLEND_SHAPES = {
    "happy": "Joy",
    "angry": "Angry",
    "sad": "Sorrow",
    "relaxed": "Relief",
    "surprised": "Surprise",
    "neutral": "Neutral",
    "blink": "Blink",
    "blink_left": "BlinkLeft",
    "blink_right": "BlinkRight",
    "aa": "Aa",
    "ih": "Ih",
    "ou": "Ou",
    "ee": "Ee",
    "oh": "Oh",
    "look_up": "LookUp",
    "look_down": "LookDown",
    "look_left": "LookLeft",
    "look_right": "LookRight",
}

# Preset expressions for quick control
EXPRESSION_PRESETS = {
    "happy":    {"Joy": 0.8, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.3},
    "angry":    {"Joy": 0.0, "Angry": 0.9, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.1},
    "sad":      {"Joy": 0.0, "Angry": 0.0, "Sorrow": 0.8, "Surprise": 0.0, "Blink": 0.5},
    "surprised":{"Joy": 0.0, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.9, "Blink": 0.0},
    "neutral":  {"Joy": 0.1, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.2},
    "wink":     {"Joy": 0.3, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 1.0, "BlinkLeft": 1.0, "BlinkRight": 0.0},
    "thinking": {"Joy": 0.0, "Angry": 0.1, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.4, "LookUp": 0.6},
    "laughing": {"Joy": 1.0, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.0, "Aa": 0.7},
}


class BlendshapeRequest(BaseModel):
    shape: str
    intensity: float = 1.0


class ExpressionRequest(BaseModel):
    expression: str
    duration_ms: Optional[int] = None


class MultiBlendshapeRequest(BaseModel):
    shapes: dict  # {"Joy": 0.8, "Blink": 0.3, ...}


def send_vmc_blendshape(shape_name: str, intensity: float):
    """Send a single blendshape value via VMC/OSC over UDP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msg = osc_message_builder.OscMessageBuilder(address="/vmc/blend/val")
    msg.add_arg(shape_name)
    msg.add_arg(float(intensity))
    packet = msg.build()
    sock.sendto(packet.dgram, (VMC_IP, VMC_PORT))
    sock.close()


def send_vmc_blendshapes(shapes: dict):
    """Send multiple blendshape values via VMC protocol."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for shape_name, intensity in shapes.items():
        msg = osc_message_builder.OscMessageBuilder(address="/vmc/blend/val")
        msg.add_arg(shape_name)
        msg.add_arg(float(intensity))
        packet = msg.build()
        sock.sendto(packet.dgram, (VMC_IP, VMC_PORT))
    sock.close()


def reset_face():
    """Reset all blendshapes to neutral."""
    neutral = {v: 0.0 for v in BLEND_SHAPES.values()}
    neutral["Neutral"] = 1.0
    neutral["Blink"] = 0.2
    send_vmc_blendshapes(neutral)


@app.post("/blendshape")
def set_blendshape(req: BlendshapeRequest):
    """Set a single blendshape on the VRM avatar."""
    vrm_name = BLEND_SHAPES.get(req.shape.lower(), req.shape)
    send_vmc_blendshape(vrm_name, max(0.0, min(1.0, req.intensity)))
    logger.info(f"Blendshape: {vrm_name} = {req.intensity}")
    return {"shape": vrm_name, "intensity": req.intensity}


@app.post("/blendshapes")
def set_multiple_blendshapes(req: MultiBlendshapeRequest):
    """Set multiple blendshapes at once."""
    mapped = {}
    for shape, intensity in req.shapes.items():
        vrm_name = BLEND_SHAPES.get(shape.lower(), shape)
        mapped[vrm_name] = max(0.0, min(1.0, float(intensity)))
    send_vmc_blendshapes(mapped)
    logger.info(f"Multi-blendshapes: {mapped}")
    return {"shapes": mapped}


@app.post("/expression")
def set_expression(req: ExpressionRequest):
    """Apply a preset expression to the VRM avatar."""
    if req.expression.lower() not in EXPRESSION_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown expression: {req.expression}. Available: {list(EXPRESSION_PRESETS.keys())}")
    preset = EXPRESSION_PRESETS[req.expression.lower()]
    send_vmc_blendshapes(preset)
    logger.info(f"Expression: {req.expression}")
    return {"expression": req.expression, "shapes": preset}


@app.post("/reset")
def reset_avatar():
    """Reset avatar to neutral pose."""
    reset_face()
    logger.info("Avatar reset to neutral")
    return {"status": "reset"}


@app.get("/expressions")
def list_expressions():
    """List all available preset expressions."""
    return {"expressions": list(EXPRESSION_PRESETS.keys()), "blendshapes": list(BLEND_SHAPES.keys())}


@app.get("/health")
def health():
    return {"status": "ok", "vmc_target": f"{VMC_IP}:{VMC_PORT}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
